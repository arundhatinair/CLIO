import io
import os
import tempfile

import pandas as pd
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from modules.visualization import create_visualization


# ==================== STYLES ====================

def _build_styles():
    """Return a dict of ReportLab ParagraphStyle objects matching the CLIO palette."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            'CLIOTitle', parent=base['Heading1'],
            fontName='Helvetica-Bold', fontSize=24,
            textColor=colors.HexColor('#3B82F6'),
            spaceAfter=12, alignment=TA_CENTER,
        ),
        "heading": ParagraphStyle(
            'CLIOHeading', parent=base['Heading2'],
            fontName='Helvetica-Bold', fontSize=14,
            textColor=colors.HexColor('#60A5FA'),
            spaceAfter=8, spaceBefore=16,
        ),
        "body": ParagraphStyle(
            'CLIOBody', parent=base['Normal'],
            fontName='Helvetica', fontSize=10,
            textColor=colors.HexColor('#1E293B'),
            spaceAfter=8,
        ),
        "code": ParagraphStyle(
            'CLIOCode', parent=base['Code'],
            fontName='Courier', fontSize=9,
            textColor=colors.HexColor('#334155'),
            leftIndent=20, spaceAfter=8,
        ),
    }


# ==================== HELPERS ====================

def _chart_to_temp_image(fig, temp_files):
    """
    Export a Plotly figure to a temporary PNG file.
    Appends the path to temp_files for later cleanup.
    Returns the file path, or None on failure.
    """
    try:
        img_bytes = fig.to_image(format="png", width=700, height=400, scale=2)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        tmp.write(img_bytes)
        tmp.close()
        temp_files.append(tmp.name)
        return tmp.name
    except Exception:
        return None


def _add_chart(story, fig, temp_files, styles):
    """Add a single Plotly chart as an embedded image to the PDF story."""
    path = _chart_to_temp_image(fig, temp_files)
    if path:
        story.append(RLImage(path, width=6 * inch, height=3.5 * inch))
        story.append(Spacer(1, 0.15 * inch))
    else:
        story.append(Paragraph(
            "<i>Note: Chart visualization requires 'kaleido'. "
            "Install with: pip install kaleido</i>",
            styles["body"],
        ))
        story.append(Spacer(1, 0.1 * inch))


def _build_data_table(df):
    """Convert the first 10 rows of a DataFrame into a styled ReportLab Table."""
    df_subset = df.head(10)
    rows = [df_subset.columns.tolist()]
    for _, row in df_subset.iterrows():
        formatted = []
        for val in row:
            if pd.isna(val):
                formatted.append('')
            elif isinstance(val, float):
                formatted.append(f'{val:,.2f}')
            else:
                formatted.append(str(val))
        rows.append(formatted)

    num_cols = len(df_subset.columns)
    col_width = 7.5 * inch / num_cols

    t = Table(rows, repeatRows=1, colWidths=[col_width] * num_cols)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F1F5F9')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1E293B')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return t


# ==================== MAIN EXPORT ====================

def generate_pdf_report(report_data):
    """
    Build a premium PDF report from a list of session query items.

    Each item in report_data should be a dict with keys:
        question, sql, summary, df, viz_type, viz_config, timestamp

    Returns a BytesIO buffer containing the completed PDF.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    styles = _build_styles()
    temp_files = []
    story = []

    # ── Cover header ──────────────────────────────────────────────────────
    story.append(Paragraph("CLIO", styles["title"]))
    story.append(Paragraph("Financial Data Intelligence Report", styles["body"]))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["body"]))
    story.append(Spacer(1, 0.3 * inch))

    # ── One section per query ─────────────────────────────────────────────
    for idx, item in enumerate(report_data, 1):
        story.append(Paragraph(f"Query {idx}: {item['question']}", styles["heading"]))
        story.append(Paragraph(f"<b>Summary:</b> {item['summary']}", styles["body"]))
        story.append(Spacer(1, 0.1 * inch))

        # SQL / label
        story.append(Paragraph("<b>SQL Query:</b>", styles["body"]))
        sql_escaped = item['sql'].replace('<', '&lt;').replace('>', '&gt;')
        story.append(Paragraph(
            f"<font name='Courier' size='8'>{sql_escaped}</font>", styles["code"]
        ))
        story.append(Spacer(1, 0.15 * inch))

        # Charts
        viz_type = item.get('viz_type')
        viz_config = item.get('viz_config', {})

        if viz_type in ('market_single', 'market_comparison', 'competitor_analysis'):
            story.append(Paragraph("<b>Market Analysis Visualizations:</b>", styles["body"]))
            story.append(Spacer(1, 0.05 * inch))

            if viz_type == 'market_single':
                if viz_config.get('price_chart'):
                    _add_chart(story, viz_config['price_chart'], temp_files, styles)
            else:
                for key in ('stock_chart', 'metric_chart'):
                    if viz_config.get(key):
                        _add_chart(story, viz_config[key], temp_files, styles)

        elif viz_type not in ('stat_cards', 'empty', 'table', None):
            fig = create_visualization(viz_type, viz_config)
            if fig:
                story.append(Paragraph("<b>Visualization:</b>", styles["body"]))
                story.append(Spacer(1, 0.05 * inch))
                _add_chart(story, fig, temp_files, styles)

        # Data table
        if item.get('df') is not None and not item['df'].empty:
            story.append(Paragraph("<b>Data Sample (First 10 Rows):</b>", styles["body"]))
            story.append(Spacer(1, 0.05 * inch))
            story.append(_build_data_table(item['df']))

        story.append(Spacer(1, 0.2 * inch))
        if idx < len(report_data):
            story.append(PageBreak())

    # ── Build PDF then clean up temp images ───────────────────────────────
    doc.build(story)
    for path in temp_files:
        try:
            os.unlink(path)
        except Exception:
            pass

    buffer.seek(0)
    return buffer
