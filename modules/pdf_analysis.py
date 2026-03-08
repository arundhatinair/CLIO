import base64
import json
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime


# ==================== DEPENDENCY CHECKS ====================

def pdf_available():
    """Return True if PyMuPDF (fitz) is installed."""
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False


def rag_available():
    """Return True if all RAG dependencies are installed."""
    try:
        from langchain_community.vectorstores import Chroma  # noqa: F401
        try:
            from langchain_huggingface import HuggingFaceEmbeddings  # noqa: F401
        except ImportError:
            from langchain_community.embeddings import HuggingFaceEmbeddings  # noqa: F401
        return True
    except ImportError:
        return False


# ==================== INDEXING ====================

def index_pdf_for_chat(pdf_bytes, pdf_name):
    """
    Parse and embed a PDF into an in-memory Chroma vector store.
    Stores per-block bounding box metadata for citation highlighting.

    Returns: (vectorstore, page_count)
    """
    import fitz
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_core.documents import Document
    from langchain_community.vectorstores import Chroma
    import chromadb

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_count = len(doc)
    all_docs = []

    for pn in range(page_count):
        page = doc[pn]
        rect = page.rect
        for blk in page.get_text("blocks"):
            txt = blk[4].strip()
            if len(txt) < 30:
                continue
            all_docs.append(Document(
                page_content=txt,
                metadata={
                    "page": pn,
                    "bbox": json.dumps([blk[0], blk[1], blk[2], blk[3]]),
                    "page_w": rect.width,
                    "page_h": rect.height,
                },
            ))

    splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=60)
    splits = splitter.split_documents(all_docs)

    emb = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    # Sanitise collection name for Chroma (alphanumeric, dots, hyphens only)
    safe = "".join(c if c.isalnum() or c in (".", "-") else "_" for c in pdf_name)
    safe = safe[:60].strip("_.-") or "pdfdoc"
    if not safe[0].isalnum():
        safe = "p" + safe
    if not safe[-1].isalnum():
        safe = safe + "0"
    if len(safe) < 3:
        safe = safe.ljust(3, "0")

    vs = Chroma.from_documents(splits, emb, client=chromadb.EphemeralClient(), collection_name=safe)
    return vs, page_count


# ==================== CHAT (RAG) ====================

def chat_with_pdf(question, vectorstore, pdf_name, history):
    """
    RAG pipeline: retrieve relevant chunks → Gemini → structured JSON response.

    Returns:
        dict with keys: answer (str), citations (list), chart (go.Figure | None)
    """
    docs = vectorstore.similarity_search(question, k=6)

    context = "\n\n".join(
        f"[SOURCE {i} | Page {d.metadata.get('page', 0) + 1}]\n{d.page_content}"
        for i, d in enumerate(docs)
    )

    history_str = "".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}\n"
        for m in history[-4:]
    )

    prompt = f"""You are a financial analyst assistant. Answer questions about "{pdf_name}" using ONLY the provided source passages.

CONVERSATION HISTORY:
{history_str}

SOURCE PASSAGES:
{context}

QUESTION: {question}

Respond in this EXACT JSON format (no markdown, no backticks):
{{
  "answer": "Your detailed answer here. Reference specific numbers and facts from the sources.",
  "citations": [
    {{"source_index": 0, "page": 1, "excerpt": "exact short quote from source (max 15 words)"}}
  ],
  "chart": {{
    "type": "bar",
    "title": "Chart title",
    "labels": ["Label1", "Label2"],
    "values": [100, 200],
    "unit": "$B"
  }}
}}

Rules:
- citations: include 1-3 of the most relevant sources. source_index matches [SOURCE N]. page is the page number shown.
- chart: ONLY include if the answer contains 2+ comparable numbers worth visualising. Set to null otherwise.
- answer: be specific, cite exact figures. 2-4 sentences.

JSON response:"""

    response = st.session_state._genai_client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt
    )
    raw = response.text.strip()

    # Strip markdown fences if Gemini adds them
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        data = json.loads(raw)
        answer = data.get("answer", raw)
        raw_cit = data.get("citations", [])
        chart_d = data.get("chart")

        citations = []
        for c in raw_cit:
            idx = c.get("source_index", 0)
            if idx < len(docs):
                d = docs[idx]
                try:
                    bbox = json.loads(d.metadata.get("bbox", "null"))
                except Exception:
                    bbox = None
                citations.append({
                    "page": d.metadata.get("page", 0),
                    "excerpt": c.get("excerpt", d.page_content[:80]),
                    "bbox": bbox,
                })

        return {
            "answer": answer,
            "citations": citations,
            "chart": _build_pdf_chart(chart_d) if chart_d else None,
        }

    except Exception:
        return {"answer": raw, "citations": [], "chart": None}


# ==================== CHART BUILDER ====================

_COLORS = ["#3B82F6", "#8B5CF6", "#10B981", "#F59E0B", "#EF4444", "#06B6D4"]


def _build_pdf_chart(cdata):
    """Build a dark-themed Plotly chart from a Gemini-generated chart spec dict."""
    if not cdata:
        return None
    try:
        ctype = cdata.get("type", "bar")
        title = cdata.get("title", "")
        labels = cdata.get("labels", [])
        unit = cdata.get("unit", "")
        values = []
        for v in cdata.get("values", []):
            try:
                values.append(float(
                    str(v).replace(",", "").replace("%", "").replace("$", "")
                          .replace("B", "").replace("M", "").strip() or 0
                ))
            except Exception:
                values.append(0)

        if not labels or not values or len(labels) != len(values):
            return None

        if ctype == "pie":
            fig = go.Figure(go.Pie(
                labels=labels, values=values, hole=0.4,
                marker_colors=_COLORS[:len(labels)], textfont_size=11,
            ))
        elif ctype == "line":
            fig = go.Figure(go.Scatter(
                x=labels, y=values, mode="lines+markers",
                line=dict(color="#3B82F6", width=2.5),
                marker=dict(size=7, color="#8B5CF6"),
                fill="tozeroy", fillcolor="rgba(59,130,246,0.08)",
            ))
        else:
            fig = go.Figure(go.Bar(
                x=labels, y=values,
                marker_color=_COLORS[:len(labels)] if len(labels) <= 6 else "#3B82F6",
                text=[f"{v:,.1f}{unit}" for v in values],
                textposition="outside", textfont_size=10,
            ))

        fig.update_layout(
            title=dict(text=title, font=dict(color="#E2E8F0", size=13, family="IBM Plex Sans")),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94A3B8", family="IBM Plex Sans", size=10),
            margin=dict(l=8, r=8, t=40, b=8), height=280,
            xaxis=dict(gridcolor="rgba(59,130,246,0.1)", tickfont_size=9),
            yaxis=dict(gridcolor="rgba(59,130,246,0.1)", tickfont_size=9),
            showlegend=(ctype == "pie"),
        )
        return fig
    except Exception:
        return None


# ==================== PAGE RENDERER ====================

def render_pdf_page_highlighted(pdf_bytes, page_num, highlight_chunks, scale=2.0):
    """
    Render a PDF page to a base64-encoded PNG, with cited text blocks highlighted.
    """
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_num]

    for chunk in highlight_chunks:
        if chunk.get("page") == page_num and chunk.get("bbox"):
            b = chunk["bbox"]
            rect = fitz.Rect(b[0], b[1], b[2], b[3])
            page.draw_rect(rect, color=(0.98, 0.75, 0.15), fill=(0.98, 0.75, 0.15), fill_opacity=0.35)
            page.draw_rect(rect, color=(0.98, 0.75, 0.15), fill=None, width=1.5)

    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    return base64.b64encode(pix.tobytes("png")).decode()
