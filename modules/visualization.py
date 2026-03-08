import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


# ==================== THEME HELPER ====================

def _apply_clio_theme(fig, title_text, x_title=None, y_title=None,
                      show_legend=True, height=350, **kwargs):
    """Apply consistent CLIO dark styling to any Plotly figure."""
    layout = {
        'plot_bgcolor': 'rgba(15, 23, 42, 0.3)',
        'paper_bgcolor': 'rgba(15, 23, 42, 0)',
        'font': {'family': 'IBM Plex Sans, sans-serif', 'color': '#E2E8F0', 'size': 11},
        'title': {
            'text': title_text,
            'font': {'family': 'Rajdhani, sans-serif', 'size': 16, 'color': '#60A5FA'},
            'x': 0.5, 'xanchor': 'center', 'y': 0.95, 'yanchor': 'top',
        },
        'showlegend': show_legend,
        'legend': {
            'font': {'size': 10},
            'bgcolor': 'rgba(30, 41, 59, 0.6)',
            'bordercolor': 'rgba(59, 130, 246, 0.2)',
            'borderwidth': 1,
        },
        'height': height,
        'xaxis': {
            'title': {'text': x_title, 'font': {'size': 12, 'color': '#94A3B8'}} if x_title else {},
            'gridcolor': 'rgba(59, 130, 246, 0.08)',
            'linecolor': 'rgba(59, 130, 246, 0.2)',
            'tickfont': {'size': 10},
        },
        'yaxis': {
            'title': {'text': y_title, 'font': {'size': 12, 'color': '#94A3B8'}} if y_title else {},
            'gridcolor': 'rgba(59, 130, 246, 0.08)',
            'linecolor': 'rgba(59, 130, 246, 0.2)',
            'tickfont': {'size': 10},
        },
    }
    layout.update(kwargs)
    fig.update_layout(**layout)
    return fig


def _fmt(text):
    """Convert snake_case column name to Title Case label."""
    return text.replace('_', ' ').title()


# ==================== AUTO-DETECTION ====================

def detect_visualization_type(df):
    """
    Choose the best chart type automatically based on data shape and column types.
    Returns: (viz_type: str, config: dict)
    """
    if df.empty:
        return "empty", {}

    num_rows, num_cols = len(df), len(df.columns)
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    text_cols = df.select_dtypes(include=['object']).columns.tolist()
    date_cols = [c for c in df.columns if 'date' in c.lower() or 'time' in c.lower()]

    if num_rows <= 3 and num_cols <= 3:
        return "stat_cards", {"data": df}

    if date_cols and numeric_cols:
        return "line_chart", {"x": date_cols[0], "y": numeric_cols, "data": df}

    if len(text_cols) == 1 and numeric_cols:
        if num_rows <= 10:
            return "bar_chart", {"x": text_cols[0], "y": numeric_cols[0], "data": df}
        return "horizontal_bar", {"x": numeric_cols[0], "y": text_cols[0], "data": df}

    if len(text_cols) == 1 and len(numeric_cols) == 1 and num_rows <= 8:
        return "donut_chart", {"labels": text_cols[0], "values": numeric_cols[0], "data": df}

    if len(numeric_cols) >= 2 and num_rows > 5:
        return "scatter_plot", {"x": numeric_cols[0], "y": numeric_cols[1], "data": df}

    if len(numeric_cols) == 1 and num_rows > 10:
        return "histogram", {"x": numeric_cols[0], "data": df}

    if len(numeric_cols) > 1 and text_cols:
        return "grouped_bar", {"x": text_cols[0], "y": numeric_cols, "data": df}

    return "table", {"data": df}


def get_available_visualizations(df):
    """
    Return all applicable visualization types for the given DataFrame.
    Returns: list of (viz_type, display_name, description) tuples
    """
    if df is None or df.empty:
        return []

    num_rows, num_cols = len(df), len(df.columns)
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    text_cols = df.select_dtypes(include=['object']).columns.tolist()
    date_cols = [c for c in df.columns if 'date' in c.lower() or 'time' in c.lower()]

    available = [('table', '📋 Table View', 'Display data as a table')]

    if num_rows <= 3 and num_cols <= 5:
        available.append(('stat_cards', '💳 Metric Cards', 'Show as metric cards'))
    if date_cols and numeric_cols:
        available.append(('line_chart', '📈 Line Chart', 'Trend over time'))
        available.append(('area_chart', '📈 Area Chart', 'Cumulative trends'))
    if text_cols and numeric_cols:
        if num_rows <= 20:
            available.append(('bar_chart', '📊 Bar Chart', 'Compare categories'))
        if num_rows > 10:
            available.append(('horizontal_bar', '↔️ Horizontal Bar', f'Top {min(15, num_rows)} items'))
    if text_cols and numeric_cols and num_rows <= 10:
        available.append(('donut_chart', '🍩 Donut Chart', 'Show proportions'))
    if len(numeric_cols) >= 2 and num_rows > 5:
        available.append(('scatter_plot', '⚫ Scatter Plot', 'Correlation between metrics'))
    if numeric_cols and num_rows > 10:
        available.append(('histogram', '📊 Histogram', 'Value distribution'))
        available.append(('box_plot', '📦 Box Plot', 'Statistical distribution'))
    if len(numeric_cols) > 1 and text_cols and num_rows <= 15:
        available.append(('grouped_bar', '📊 Grouped Bar', 'Compare multiple metrics'))
    if len(numeric_cols) >= 3 and 3 <= num_rows <= 20:
        available.append(('heatmap', '🔥 Heatmap', 'Show patterns in data'))

    return available


def build_viz_config(df, viz_type):
    """Build a config dict suitable for create_visualization() for the given viz_type."""
    if df is None or df.empty:
        return {"data": df}

    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    text_cols = df.select_dtypes(include=['object']).columns.tolist()
    date_cols = [c for c in df.columns if 'date' in c.lower() or 'time' in c.lower()]

    mapping = {
        "table": lambda: {"data": df},
        "stat_cards": lambda: {"data": df},
        "heatmap": lambda: {"data": df},
        "box_plot": lambda: {"data": df},
        "line_chart": lambda: {"x": (date_cols or text_cols or [None])[0], "y": numeric_cols, "data": df},
        "area_chart": lambda: {"x": (date_cols or text_cols or [None])[0], "y": numeric_cols, "data": df},
        "bar_chart": lambda: {"x": (text_cols or [None])[0], "y": (numeric_cols or [None])[0], "data": df},
        "horizontal_bar": lambda: {"x": (numeric_cols or [None])[0], "y": (text_cols or [None])[0], "data": df},
        "donut_chart": lambda: {"labels": (text_cols or [None])[0], "values": (numeric_cols or [None])[0], "data": df},
        "scatter_plot": lambda: {"x": (numeric_cols or [None])[0], "y": (numeric_cols[1:] or [None])[0], "data": df},
        "histogram": lambda: {"x": (numeric_cols or [None])[0], "data": df},
        "grouped_bar": lambda: {"x": (text_cols or [None])[0], "y": numeric_cols, "data": df},
    }

    builder = mapping.get(viz_type)
    return builder() if builder else {"data": df}


# ==================== CHART RENDERING ====================

def create_visualization(viz_type, config):
    """
    Render a Plotly figure for the given viz_type and config dict.
    Returns a go.Figure, or None for types handled outside (stat_cards, table, empty).
    """
    df = config.get('data')

    if viz_type in ("empty", "stat_cards"):
        return None

    # ── Line chart ────────────────────────────────────────────────────────
    if viz_type == "line_chart":
        x_col, y_cols = config['x'], config['y']
        fig = go.Figure()
        for y in y_cols:
            fig.add_trace(go.Scatter(
                x=df[x_col], y=df[y], mode='lines+markers', name=_fmt(y),
                line=dict(width=2.5), marker=dict(size=6),
                hovertemplate=f'<b>%{{fullData.name}}</b><br>{_fmt(x_col)}: %{{x}}<br>Value: %{{y:,.2f}}<extra></extra>',
            ))
        title = f"{_fmt(y_cols[0])} Over {_fmt(x_col)}" if len(y_cols) == 1 else f"Trend Analysis Over {_fmt(x_col)}"
        return _apply_clio_theme(fig, title, x_title=_fmt(x_col), y_title="Value",
                                  show_legend=len(y_cols) > 1, hovermode='x unified')

    # ── Area chart ────────────────────────────────────────────────────────
    if viz_type == "area_chart":
        x_col, y_cols = config['x'], config['y']
        fig = go.Figure()
        for y in y_cols:
            fig.add_trace(go.Scatter(
                x=df[x_col], y=df[y], mode='lines', name=_fmt(y),
                fill='tonexty' if len(y_cols) > 1 else 'tozeroy',
                line=dict(width=2),
                hovertemplate=f'<b>%{{fullData.name}}</b><br>{_fmt(x_col)}: %{{x}}<br>Value: %{{y:,.2f}}<extra></extra>',
            ))
        return _apply_clio_theme(fig, f"Area Chart: {_fmt(x_col)}", x_title=_fmt(x_col),
                                  y_title="Value", show_legend=len(y_cols) > 1, hovermode='x unified')

    # ── Bar chart ─────────────────────────────────────────────────────────
    if viz_type == "bar_chart":
        x_col, y_col = config['x'], config['y']
        fig = px.bar(df, x=x_col, y=y_col, color_discrete_sequence=['#3B82F6'],
                     labels={x_col: _fmt(x_col), y_col: _fmt(y_col)})
        fig.update_traces(marker=dict(line=dict(width=0)),
                          hovertemplate=f'<b>{_fmt(x_col)}</b>: %{{x}}<br>{_fmt(y_col)}: %{{y:,.2f}}<extra></extra>')
        return _apply_clio_theme(fig, f"{_fmt(y_col)} by {_fmt(x_col)}", x_title=_fmt(x_col),
                                  y_title=_fmt(y_col), show_legend=False)

    # ── Horizontal bar ────────────────────────────────────────────────────
    if viz_type == "horizontal_bar":
        x_col, y_col = config['x'], config['y']
        df_top = df.nlargest(15, x_col)
        fig = px.bar(df_top, x=x_col, y=y_col, orientation='h',
                     color_discrete_sequence=['#8B5CF6'],
                     labels={x_col: _fmt(x_col), y_col: _fmt(y_col)})
        fig.update_traces(marker=dict(line=dict(width=0)),
                          hovertemplate=f'<b>%{{y}}</b><br>{_fmt(x_col)}: %{{x:,.2f}}<extra></extra>')
        return _apply_clio_theme(fig, f"Top 15: {_fmt(x_col)} by {_fmt(y_col)}", x_title=_fmt(x_col),
                                  y_title=_fmt(y_col), show_legend=False, height=400)

    # ── Donut chart ───────────────────────────────────────────────────────
    if viz_type == "donut_chart":
        labels_col, values_col = config['labels'], config['values']
        fig = go.Figure(data=[go.Pie(
            labels=df[labels_col], values=df[values_col], hole=0.5,
            marker=dict(colors=px.colors.sequential.Blues_r,
                        line=dict(color='rgba(15,23,42,0.8)', width=2)),
            textinfo='label+percent', textfont=dict(size=10),
            hovertemplate='<b>%{label}</b><br>Value: %{value:,.2f}<br>Pct: %{percent}<extra></extra>',
        )])
        return _apply_clio_theme(fig, f"{_fmt(values_col)} Distribution by {_fmt(labels_col)}",
                                  show_legend=True,
                                  legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02))

    # ── Scatter plot ──────────────────────────────────────────────────────
    if viz_type == "scatter_plot":
        x_col, y_col = config['x'], config['y']
        fig = px.scatter(df, x=x_col, y=y_col, color_discrete_sequence=['#60A5FA'],
                         labels={x_col: _fmt(x_col), y_col: _fmt(y_col)})
        fig.update_traces(marker=dict(size=8, line=dict(width=0.5, color='white')),
                          hovertemplate=f'{_fmt(x_col)}: %{{x:,.2f}}<br>{_fmt(y_col)}: %{{y:,.2f}}<extra></extra>')
        return _apply_clio_theme(fig, f"{_fmt(y_col)} vs {_fmt(x_col)}", x_title=_fmt(x_col),
                                  y_title=_fmt(y_col), show_legend=False)

    # ── Histogram ─────────────────────────────────────────────────────────
    if viz_type == "histogram":
        x_col = config['x']
        fig = px.histogram(df, x=x_col, nbins=20, color_discrete_sequence=['#3B82F6'],
                           labels={x_col: _fmt(x_col)})
        fig.update_traces(marker=dict(line=dict(width=0.5, color='rgba(255,255,255,0.2)')),
                          hovertemplate='Range: %{x}<br>Count: %{y}<extra></extra>')
        return _apply_clio_theme(fig, f"Distribution of {_fmt(x_col)}", x_title=_fmt(x_col),
                                  y_title="Frequency", show_legend=False)

    # ── Grouped bar ───────────────────────────────────────────────────────
    if viz_type == "grouped_bar":
        x_col, y_cols = config['x'], config['y']
        fig = go.Figure()
        for y in y_cols:
            fig.add_trace(go.Bar(
                x=df[x_col], y=df[y], name=_fmt(y),
                hovertemplate=f'<b>%{{fullData.name}}</b><br>{_fmt(x_col)}: %{{x}}<br>Value: %{{y:,.2f}}<extra></extra>',
            ))
        return _apply_clio_theme(fig, f"Comparison Across {_fmt(x_col)}", x_title=_fmt(x_col),
                                  y_title="Value", show_legend=True, barmode='group',
                                  legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

    # ── Heatmap ───────────────────────────────────────────────────────────
    if viz_type == "heatmap":
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if len(numeric_cols) < 2:
            return None
        text_cols = df.select_dtypes(include=['object']).columns.tolist()
        labels = df[text_cols[0]].tolist() if text_cols else df.index.tolist()
        fig = go.Figure(data=go.Heatmap(
            z=df[numeric_cols].values,
            x=[_fmt(c) for c in numeric_cols],
            y=labels,
            colorscale='Blues',
            hovertemplate='%{y}<br>%{x}: %{z:,.2f}<extra></extra>',
        ))
        return _apply_clio_theme(fig, "Data Heatmap", x_title="Metrics", y_title="Items", show_legend=False)

    # ── Box plot ──────────────────────────────────────────────────────────
    if viz_type == "box_plot":
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if not numeric_cols:
            return None
        fig = go.Figure()
        for col in numeric_cols[:5]:
            fig.add_trace(go.Box(y=df[col], name=_fmt(col), boxmean='sd'))
        return _apply_clio_theme(fig, "Statistical Distribution", x_title="Metrics",
                                  y_title="Values", show_legend=False)

    return None


# ==================== STREAMLIT RENDER HELPERS ====================

def render_viz_selector(df, query_index, current_viz):
    """
    Render the chart-type dropdown and return the selected viz_type.
    Persists the user's choice in st.session_state.user_viz_selection.
    """
    available = get_available_visualizations(df)
    if not available:
        return current_viz, current_viz

    viz_types = [v[0] for v in available]
    viz_options = [v[1] for v in available]

    # Respect stored user preference
    stored = st.session_state.user_viz_selection.get(query_index, current_viz)
    try:
        current_index = viz_types.index(stored)
    except ValueError:
        current_index = 0

    st.markdown("**📊 Chart Type:**")
    selected_display = st.selectbox(
        "Choose visualization",
        options=viz_options,
        index=current_index,
        key=f"viz_selector_{query_index}",
        label_visibility="collapsed",
    )
    selected_type = viz_types[viz_options.index(selected_display)]
    selected_desc = next(v[2] for v in available if v[0] == selected_type)
    st.markdown(f"<small style='color:#94A3B8;'>💡 {selected_desc}</small>", unsafe_allow_html=True)
    return selected_type, selected_display


def render_visualization(df, viz_type, viz_config, query_index):
    """
    Render the chart or table for a given viz_type, including the data table below.
    Handles stat_cards and table types inline.
    """
    if viz_type == "stat_cards":
        cols = st.columns(min(len(df.columns), 4))
        for i, col_name in enumerate(df.columns[:4]):
            with cols[i]:
                st.metric(label=col_name, value=df[col_name].iloc[0])
    elif viz_type == "table":
        st.dataframe(df, use_container_width=True, height=350)
    else:
        fig = create_visualization(viz_type, viz_config)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Could not generate this visualization type. Showing table instead.")
            st.dataframe(df, use_container_width=True, height=350)

    st.markdown("---")
    st.markdown("**📋 Data Table**")
    st.dataframe(df, use_container_width=True, height=200)
