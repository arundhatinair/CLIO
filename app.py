"""
CLIO — Financial Data Intelligence
Entry point: initialises config, session state, and routes between the three analysis modes.
"""

import os
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv
from google import genai

# ── Internal modules ──────────────────────────────────────────────────────────
from modules.styles import inject_css, render_header
from modules.database import (
    get_db_connection, validate_database, get_schema_info,
    generate_sql_from_question, execute_sql_query, generate_summary_from_results,
)
from modules.market import detect_market_data_query, generate_market_data_analysis
from modules.visualization import (
    detect_visualization_type, build_viz_config,
    render_viz_selector, render_visualization,
)
from modules.pdf_analysis import (
    pdf_available, rag_available,
    index_pdf_for_chat, chat_with_pdf, render_pdf_page_highlighted,
)
from modules.report import generate_pdf_report


# ==================== PAGE CONFIG ====================

st.set_page_config(
    page_title="CLIO | Financial Data Intelligence",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ==================== BOOTSTRAP ====================

inject_css()

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    st.error("⚠️ Google API Key not found. Configure .env file.")
    st.stop()

genai_client = genai.Client(api_key=api_key)
st.session_state._genai_client = genai_client


# ==================== SESSION STATE ====================

_defaults = {
    "analysis_mode": "Internal Database",
    "messages": [],
    "report_items": [],
    "conversation_count": 0,
    "user_viz_selection": {},
    # PDF mode
    "pdf_bytes": None,
    "pdf_name": "",
    "pdf_vectorstore": None,
    "pdf_page_count": 0,
    "pdf_current_page": 0,
    "pdf_messages": [],
    "pdf_active_cits": [],
}
for key, default in _defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ==================== HEADER + MODE SELECTOR ====================

render_header()

st.markdown("""
<div class="mode-selector-container">
    <div class="mode-selector-title">📊 Analysis Mode</div>
</div>
""", unsafe_allow_html=True)

_, col_mid, _ = st.columns([1, 3, 1])
with col_mid:
    selected_mode = st.radio(
        "Choose your data source:",
        options=[
            "📂 Internal Database",
            "🌍 Market Data (Stocks, Crypto, Forex, etc.)",
            "📄 PDF Report Analysis",
        ],
        index={"Internal Database": 0, "Market Data": 1, "PDF Analysis": 2}.get(
            st.session_state.analysis_mode, 0
        ),
        horizontal=True,
        label_visibility="collapsed",
        key="mode_selector",
    )

    if "Internal Database" in selected_mode:
        st.session_state.analysis_mode = "Internal Database"
    elif "Market Data" in selected_mode:
        st.session_state.analysis_mode = "Market Data"
    else:
        st.session_state.analysis_mode = "PDF Analysis"

    _descriptions = {
        "Internal Database": "🔍 Analyze your company's financial data via natural language SQL queries",
        "Market Data":       "🌐 Analyze public financial markets — stocks, indices, ETFs, forex, crypto",
        "PDF Analysis":      "📄 Chat with a financial report PDF — citations, highlights & auto-charts",
    }
    st.markdown(
        f"<div style='text-align:center;color:#94A3B8;font-size:0.85rem;margin-top:0.5rem;'>"
        f"{_descriptions[st.session_state.analysis_mode]}</div>",
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)


# ==================== PDF ANALYSIS MODE ====================

if st.session_state.analysis_mode == "PDF Analysis":

    pdf_ok = pdf_available()
    rag_ok = rag_available()

    if not pdf_ok or not rag_ok:
        missing = []
        if not pdf_ok:
            missing.append("`pymupdf`")
        if not rag_ok:
            missing.append("`langchain-community` `langchain-huggingface` `sentence-transformers` `chromadb`")
        st.error(f"⚠️ Missing packages: {', '.join(missing)}")
        st.code(
            "pip install pymupdf langchain-core langchain-community "
            "langchain-text-splitters langchain-huggingface sentence-transformers chromadb"
        )

    else:
        # ── Upload ────────────────────────────────────────────────────────
        up1, up2 = st.columns([3, 1])
        with up1:
            uploaded_pdf = st.file_uploader(
                "Upload PDF", type=["pdf"], key="pdf_uploader", label_visibility="collapsed"
            )
        with up2:
            if st.session_state.pdf_name:
                st.markdown(
                    f"<div style='color:#60A5FA;font-size:0.75rem;padding-top:0.6rem;"
                    f"overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'>"
                    f"📄 {st.session_state.pdf_name}</div>",
                    unsafe_allow_html=True,
                )

        if uploaded_pdf and st.session_state.pdf_name != uploaded_pdf.name:
            with st.spinner("📑 Indexing PDF — this takes ~30s on first load…"):
                try:
                    raw = uploaded_pdf.read()
                    vs, pc = index_pdf_for_chat(raw, uploaded_pdf.name)
                    st.session_state.pdf_bytes = raw
                    st.session_state.pdf_name = uploaded_pdf.name
                    st.session_state.pdf_vectorstore = vs
                    st.session_state.pdf_page_count = pc
                    st.session_state.pdf_current_page = 0
                    st.session_state.pdf_messages = []
                    st.session_state.pdf_active_cits = []
                    st.toast(f"✅ {pc} pages indexed", icon="📑")
                except Exception as e:
                    st.error(f"Indexing error: {e}")

        if st.session_state.pdf_bytes:
            col1, col2, col3 = st.columns([1, 1, 1])

            # ── Chat column ───────────────────────────────────────────────
            with col1:
                st.markdown(
                    '<div class="pdf-col"><div class="pdf-col-hdr">💬 Chat with PDF</div>'
                    '<div class="pdf-col-body">',
                    unsafe_allow_html=True,
                )

                for msg in st.session_state.pdf_messages:
                    if msg["role"] == "user":
                        st.markdown(
                            f'<div class="chat-bubble-user">{msg["content"]}</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f'<div class="chat-bubble-ai">{msg["content"]}</div>',
                            unsafe_allow_html=True,
                        )
                        cits = msg.get("citations", [])
                        if cits:
                            chips = "".join(
                                f'<span class="cit-chip">📄 p{c["page"]+1} — {c["excerpt"][:40]}…</span> '
                                for c in cits
                            )
                            st.markdown(
                                f'<div style="margin-bottom:0.6rem;">{chips}</div>',
                                unsafe_allow_html=True,
                            )
                            chip_cols = st.columns(min(len(cits), 3))
                            for i, c in enumerate(cits[:3]):
                                with chip_cols[i]:
                                    if st.button(f"→ p{c['page']+1}",
                                                 key=f"cit_{msg.get('ts','')}__{i}",
                                                 use_container_width=True):
                                        st.session_state.pdf_current_page = c["page"]
                                        st.session_state.pdf_active_cits = cits
                                        st.rerun()

                st.markdown('</div></div>', unsafe_allow_html=True)

                if prompt := st.chat_input("Ask anything about the document…"):
                    st.session_state.pdf_messages.append({"role": "user", "content": prompt})
                    with st.spinner("🧠 Searching document…"):
                        try:
                            result = chat_with_pdf(
                                prompt,
                                st.session_state.pdf_vectorstore,
                                st.session_state.pdf_name,
                                st.session_state.pdf_messages,
                            )
                            ts = datetime.now().strftime("%H:%M:%S")
                            st.session_state.pdf_messages.append({
                                "role": "assistant",
                                "content": result["answer"],
                                "citations": result["citations"],
                                "chart": result["chart"],
                                "ts": ts,
                            })
                            if result["citations"]:
                                st.session_state.pdf_current_page = result["citations"][0]["page"]
                                st.session_state.pdf_active_cits = result["citations"]
                        except Exception as ex:
                            st.session_state.pdf_messages.append({
                                "role": "assistant", "content": f"❌ Error: {ex}",
                                "citations": [], "chart": None, "ts": "",
                            })
                    st.rerun()

            # ── Viewer column ─────────────────────────────────────────────
            with col2:
                cur_page = st.session_state.pdf_current_page
                page_count = st.session_state.pdf_page_count
                active_cits = st.session_state.pdf_active_cits

                st.markdown(
                    '<div class="pdf-col"><div class="pdf-col-hdr">📄 Document Viewer</div>'
                    '<div class="pdf-col-body" style="padding:0.5rem;">',
                    unsafe_allow_html=True,
                )

                n1, n2, n3, n4 = st.columns([1, 1, 3, 1])
                with n1:
                    if st.button("◀", key="pv_prev", disabled=cur_page == 0, use_container_width=True):
                        st.session_state.pdf_current_page -= 1
                        st.session_state.pdf_active_cits = []
                        st.rerun()
                with n2:
                    if st.button("▶", key="pv_next", disabled=cur_page >= page_count - 1, use_container_width=True):
                        st.session_state.pdf_current_page += 1
                        st.session_state.pdf_active_cits = []
                        st.rerun()
                with n3:
                    st.markdown(
                        f"<div style='text-align:center;color:#94A3B8;font-size:0.8rem;padding-top:0.45rem;'>"
                        f"Page <b style='color:#E2E8F0'>{cur_page+1}</b> / {page_count}</div>",
                        unsafe_allow_html=True,
                    )
                with n4:
                    if active_cits:
                        st.markdown(
                            "<div style='color:#FCD34D;font-size:0.7rem;padding-top:0.5rem;text-align:center;'>✨ cited</div>",
                            unsafe_allow_html=True,
                        )

                with st.spinner("Rendering…"):
                    img_b64 = render_pdf_page_highlighted(
                        st.session_state.pdf_bytes, cur_page, active_cits, scale=2.0
                    )
                st.image(f"data:image/png;base64,{img_b64}", use_container_width=True)
                st.markdown('</div></div>', unsafe_allow_html=True)

            # ── Chart + log column ────────────────────────────────────────
            with col3:
                st.markdown(
                    '<div class="pdf-col"><div class="pdf-col-hdr">📊 Visualization & Report</div>'
                    '<div class="pdf-col-body">',
                    unsafe_allow_html=True,
                )

                ai_msgs = [m for m in st.session_state.pdf_messages if m["role"] == "assistant"]
                if ai_msgs:
                    latest = ai_msgs[-1]
                    if latest.get("chart") is not None:
                        st.plotly_chart(latest["chart"], use_container_width=True,
                                        key=f"pdf_chart_{latest.get('ts','')}")
                    else:
                        st.markdown("""
                        <div class="pdf-placeholder">
                          <div class="pdf-placeholder-icon">📊</div>
                          <div style="font-size:0.8rem;color:#475569;">
                            Charts appear automatically<br>when your answer contains<br>comparable numbers
                          </div>
                        </div>""", unsafe_allow_html=True)

                    st.markdown("<hr style='border-color:rgba(59,130,246,0.15);margin:0.75rem 0;'>",
                                unsafe_allow_html=True)
                    st.markdown(
                        "<div style='font-size:0.78rem;font-weight:700;color:#60A5FA;margin-bottom:0.5rem;'>"
                        "📋 Session Log</div>",
                        unsafe_allow_html=True,
                    )

                    msgs = st.session_state.pdf_messages
                    pairs = [
                        (msgs[i]["content"], msgs[i + 1]["content"] if i + 1 < len(msgs) else "")
                        for i, m in enumerate(msgs) if m["role"] == "user"
                    ]
                    for qi, (q, a) in enumerate(pairs, 1):
                        st.markdown(f"""
                        <div style="background:rgba(30,41,59,0.5);border:1px solid rgba(59,130,246,0.12);
                             border-radius:6px;padding:0.55rem 0.7rem;margin-bottom:0.5rem;">
                          <div style="font-size:0.7rem;font-weight:700;color:#60A5FA;margin-bottom:0.2rem;">Q{qi}</div>
                          <div style="font-size:0.75rem;color:#94A3B8;margin-bottom:0.25rem;">{q}</div>
                          <div style="font-size:0.75rem;color:#CBD5E1;">{a[:120]}{"…" if len(a) > 120 else ""}</div>
                        </div>""", unsafe_allow_html=True)

                    if pairs:
                        if st.button("🗑️ Clear Chat", key="pdf_clear_chat", use_container_width=True):
                            st.session_state.pdf_messages = []
                            st.session_state.pdf_active_cits = []
                            st.rerun()
                else:
                    st.markdown("""
                    <div class="pdf-placeholder">
                      <div class="pdf-placeholder-icon">💬</div>
                      <div style="font-size:0.85rem;font-weight:600;color:#64748B;margin-bottom:0.4rem;">
                        Ask a question to begin
                      </div>
                      <div style="font-size:0.78rem;color:#334155;line-height:1.7;">
                        Try:<br>
                        <i>"What was total revenue?"</i><br>
                        <i>"Summarise the key risks"</i><br>
                        <i>"Compare iPhone vs Services growth"</i>
                      </div>
                    </div>""", unsafe_allow_html=True)

                st.markdown('</div></div>', unsafe_allow_html=True)

        else:
            st.markdown("""
            <div style="text-align:center;padding:6rem 2rem;color:#475569;">
              <div style="font-size:4rem;margin-bottom:1rem;">📄</div>
              <div style="font-size:1.05rem;font-weight:600;color:#94A3B8;margin-bottom:0.5rem;">
                Upload a financial report PDF to begin
              </div>
              <div style="font-size:0.82rem;color:#334155;line-height:1.8;">
                Annual reports · 10-K / 10-Q · Earnings releases · Analyst research
              </div>
            </div>""", unsafe_allow_html=True)


# ==================== DATABASE / MARKET DATA MODES ====================

else:
    # Validate DB only when that mode is active
    if st.session_state.analysis_mode == "Internal Database":
        validate_database()

    col1, col2, col3 = st.columns([1, 1, 1])

    # ── Column 1: Conversation ────────────────────────────────────────────
    with col1:
        st.markdown("""
        <div class="clio-column">
            <div class="column-header">
                <div class="column-title">Conversation</div>
                <div class="column-subtitle">Natural language interface</div>
            </div>
            <div class="column-content" id="conversation-content">
        """, unsafe_allow_html=True)

        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(f"""
                <div class="message-group">
                    <div class="message-user">
                        <div class="message-bubble message-bubble-user">{msg["content"]}</div>
                    </div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="message-group">
                    <div class="message-assistant">
                        <div class="message-bubble message-bubble-assistant">{msg["content"]}</div>
                    </div>
                </div>""", unsafe_allow_html=True)

                if "sql" in msg and msg["sql"] and msg.get("type") not in ("market_analysis", "competitor_analysis"):
                    with st.expander("📊 View SQL Query", expanded=False):
                        st.code(msg["sql"], language="sql")

                if msg.get("type") == "market_analysis":
                    subtype = msg.get("analysis_subtype", "comparison")
                    label = msg.get("symbol", "Unknown") if subtype == "single" else ", ".join(msg.get("symbols", []))
                    icon = "📈 Market Analysis:" if subtype == "single" else "📈 Market Comparison:"
                    st.markdown(
                        f"<div style='margin-top:0.5rem;padding:0.5rem;background:rgba(59,130,246,0.1);"
                        f"border:1px solid rgba(59,130,246,0.2);border-radius:0.25rem;font-size:0.75rem;'>"
                        f"{icon} {label}</div>",
                        unsafe_allow_html=True,
                    )

                if msg.get("type") == "competitor_analysis" and "tickers" in msg:
                    st.markdown(
                        f"<div style='margin-top:0.5rem;padding:0.5rem;background:rgba(59,130,246,0.1);"
                        f"border:1px solid rgba(59,130,246,0.2);border-radius:0.25rem;font-size:0.75rem;'>"
                        f"📈 Competitor Analysis: {', '.join(msg['tickers'])}</div>",
                        unsafe_allow_html=True,
                    )

        st.markdown("</div></div>", unsafe_allow_html=True)

        if prompt := st.chat_input("Ask CLIO anything about your financial data..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            current_mode = st.session_state.analysis_mode

            symbols, query_type = [], None
            if current_mode == "Market Data":
                _, symbols, query_type = detect_market_data_query(prompt)

            spinner_msg = (
                f"🔍 Fetching market data for {', '.join(symbols)}..." if symbols
                else ("🔍 Analyzing market data..." if current_mode == "Market Data"
                      else "🧠 CLIO is analyzing your database...")
            )

            with st.spinner(spinner_msg):
                try:
                    if current_mode == "Market Data":
                        if not symbols:
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": (
                                    "⚠️ Please specify ticker symbols for market data analysis.\n\n"
                                    "**Examples:**\n"
                                    "- Stocks: `AAPL`, `MSFT`, `GOOGL`\n"
                                    "- Indices: `^GSPC`, `^DJI`, `^IXIC`\n"
                                    "- ETFs: `SPY`, `QQQ`, `VTI`\n"
                                    "- Forex: `EURUSD=X`, `GBPUSD=X`\n"
                                    "- Commodities: `GC=F` (gold), `CL=F` (oil)\n"
                                    "- Crypto: `BTC-USD`, `ETH-USD`"
                                ),
                            })
                        else:
                            result = generate_market_data_analysis(prompt, symbols, query_type)
                            if result["success"]:
                                atype = result.get("analysis_type", "comparison")
                                msg_data = {
                                    "role": "assistant",
                                    "content": result["summary"],
                                    "type": "market_analysis",
                                    "analysis_subtype": atype,
                                    "data": result["data"],
                                }
                                if atype == "single":
                                    msg_data.update({"price_chart": result.get("price_chart"), "symbol": result.get("symbol")})
                                else:
                                    msg_data.update({
                                        "stock_chart": result.get("stock_chart"),
                                        "metric_chart": result.get("metric_chart"),
                                        "focus_metric": result.get("focus_metric"),
                                        "symbols": result.get("symbols", symbols),
                                    })
                                st.session_state.messages.append(msg_data)

                                viz_type = "market_single" if atype == "single" else "market_comparison"
                                viz_config = (
                                    {"price_chart": result.get("price_chart")} if atype == "single"
                                    else {"stock_chart": result.get("stock_chart"), "metric_chart": result.get("metric_chart")}
                                )
                                st.session_state.report_items.append({
                                    "question": prompt,
                                    "sql": f"Market Analysis: {', '.join(result.get('symbols', symbols))}",
                                    "summary": result["summary"],
                                    "df": result["data"],
                                    "viz_type": viz_type,
                                    "viz_config": viz_config,
                                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                                })
                                st.session_state.conversation_count += 1
                            else:
                                st.session_state.messages.append({
                                    "role": "assistant", "content": f"⚠️ {result['message']}"
                                })

                    else:  # Internal Database
                        conn = get_db_connection()
                        schema = get_schema_info(conn)
                        sql_query = generate_sql_from_question(schema, prompt)
                        df_results, error = execute_sql_query(conn, sql_query)

                        if error:
                            st.session_state.messages.append({
                                "role": "assistant", "content": f"⚠️ Query error: {error}"
                            })
                        elif df_results is not None:
                            summary = generate_summary_from_results(prompt, sql_query, df_results)
                            viz_type, viz_config = detect_visualization_type(df_results)
                            st.session_state.messages.append({
                                "role": "assistant", "content": summary,
                                "sql": sql_query, "data": df_results,
                                "viz_type": viz_type, "viz_config": viz_config,
                            })
                            st.session_state.report_items.append({
                                "question": prompt, "sql": sql_query, "summary": summary,
                                "df": df_results, "viz_type": viz_type, "viz_config": viz_config,
                                "timestamp": datetime.now().strftime("%H:%M:%S"),
                            })
                            st.session_state.conversation_count += 1

                except Exception as e:
                    st.session_state.messages.append({
                        "role": "assistant", "content": f"❌ System error: {str(e)}"
                    })

            st.rerun()

    # ── Column 2: Visualization ───────────────────────────────────────────
    with col2:
        st.markdown("""
        <div class="clio-column">
            <div class="column-header">
                <div class="column-title">Visualization</div>
                <div class="column-subtitle">Auto-generated insights</div>
            </div>
            <div class="column-content">
        """, unsafe_allow_html=True)

        if st.session_state.conversation_count > 0:
            latest = st.session_state.report_items[-1]
            query_index = st.session_state.conversation_count - 1
            viz_type = latest.get("viz_type")

            if viz_type in ("market_single", "market_comparison", "competitor_analysis"):
                st.markdown("### 📊 Market Analysis")
                vc = latest.get("viz_config", {})
                if viz_type == "market_single":
                    if vc.get("price_chart"):
                        st.plotly_chart(vc["price_chart"], use_container_width=True)
                else:
                    if vc.get("stock_chart"):
                        st.plotly_chart(vc["stock_chart"], use_container_width=True)
                    if vc.get("metric_chart"):
                        st.plotly_chart(vc["metric_chart"], use_container_width=True)
                st.markdown("---")
                st.markdown("**Financial Metrics**")
                st.dataframe(latest["df"], use_container_width=True, height=300)

            else:
                df = latest.get("df")
                selected_type, _ = render_viz_selector(df, query_index, latest.get("viz_type", "table"))

                if selected_type != latest.get("viz_type"):
                    st.session_state.user_viz_selection[query_index] = selected_type
                    st.session_state.report_items[query_index]["viz_type"] = selected_type
                    st.session_state.report_items[query_index]["viz_config"] = build_viz_config(df, selected_type)
                    st.rerun()

                st.markdown("---")
                render_visualization(df, selected_type, latest.get("viz_config", {}), query_index)

        else:
            st.markdown("""
            <div class="viz-placeholder">
                <div class="viz-placeholder-icon">📊</div>
                <div class="viz-placeholder-text">
                    Visualizations will appear here automatically<br>when you ask questions
                </div>
            </div>""", unsafe_allow_html=True)

        st.markdown("</div></div>", unsafe_allow_html=True)

    # ── Column 3: Report ──────────────────────────────────────────────────
    with col3:
        st.markdown("""
        <div class="clio-column">
            <div class="column-header">
                <div class="column-title">Report</div>
                <div class="column-subtitle">Session compilation</div>
            </div>
            <div class="column-content">
        """, unsafe_allow_html=True)

        if st.session_state.report_items:
            for idx, item in enumerate(st.session_state.report_items, 1):
                st.markdown(f"""
                <div class="report-item">
                    <div class="report-item-header">Query {idx} · {item['timestamp']}</div>
                    <div class="report-item-content">
                        <strong>Q:</strong> {item['question']}<br>
                        <strong>A:</strong> {item['summary'][:150]}...
                    </div>
                </div>""", unsafe_allow_html=True)

            if st.button("📄 Generate PDF Report", use_container_width=True, type="primary"):
                with st.spinner("Generating PDF..."):
                    pdf_buffer = generate_pdf_report(st.session_state.report_items)
                    st.download_button(
                        label="⬇️ Download Report",
                        data=pdf_buffer,
                        file_name=f"CLIO_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )

            if st.button("🗑️ Clear Report", use_container_width=True):
                st.session_state.report_items = []
                st.session_state.messages = []
                st.session_state.conversation_count = 0
                st.session_state.user_viz_selection = {}
                st.rerun()

        else:
            st.markdown("""
            <div class="viz-placeholder">
                <div class="viz-placeholder-icon">📋</div>
                <div class="viz-placeholder-text">
                    Your conversation will be compiled here<br>Ready for PDF export
                </div>
            </div>""", unsafe_allow_html=True)

        st.markdown("</div></div>", unsafe_allow_html=True)
