import re
import time
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf


# ==================== TICKER DETECTION ====================

# Words that look like tickers but are not
_COMMON_WORDS = {
    'SQL', 'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'NULL',
    'AI', 'CEO', 'CFO', 'USA', 'US', 'UK', 'I', 'A', 'IS', 'IT',
    'IN', 'BY', 'TO', 'OF', 'FOR', 'ON', 'AT',
}

# Market keywords that signal a market query even without a ticker symbol
_MARKET_KEYWORDS = [
    'stock price', 'stock market', 'stock ticker', 'stock exchange',
    'market index', 'market indices', 'dow jones', 's&p 500', 's&p500', 'nasdaq',
    'forex', 'currency pair', 'exchange rate',
    'cryptocurrency', 'bitcoin', 'ethereum', 'crypto price',
    'commodity price', 'gold price', 'oil price', 'futures price',
    'etf', 'mutual fund', 'publicly traded', 'ticker symbol',
    'trading volume', 'wall street', 'stock performance',
]


def detect_market_data_query(question):
    """
    Detect whether a question is asking about live market data.

    Returns:
        (is_market_query: bool, symbols: list[str], query_type: str | None)
        query_type is one of: "single", "comparison", "general", or None
    """
    question_lower = question.lower()

    # Extract standard tickers (1–5 uppercase letters)
    potential_tickers = re.findall(r'\b[A-Z]{1,5}\b', question)
    ticker_symbols = [t for t in potential_tickers if t not in _COMMON_WORDS]

    # Extract special symbol patterns (^GSPC, EURUSD=X, GC=F, BTC-USD)
    special_symbols = []
    for pattern in [r'\^[A-Z]+', r'[A-Z]+=X', r'[A-Z]+=F', r'[A-Z]+-USD']:
        special_symbols.extend(re.findall(pattern, question))

    all_symbols = ticker_symbols + special_symbols

    if all_symbols:
        query_type = "comparison" if len(all_symbols) >= 2 else "single"
        return True, all_symbols, query_type

    if any(kw in question_lower for kw in _MARKET_KEYWORDS):
        return True, [], "general"

    return False, [], None


# ==================== DATA FETCHING ====================

def format_large_number(value):
    """Format a raw numeric value as a human-readable string (e.g. $2.80T, $95.30B)."""
    if value in ('N/A', None):
        return 'N/A'
    try:
        num = float(value)
        if abs(num) >= 1_000_000_000_000:
            return f"${num / 1_000_000_000_000:.2f}T"
        elif abs(num) >= 1_000_000_000:
            return f"${num / 1_000_000_000:.2f}B"
        elif abs(num) >= 1_000_000:
            return f"${num / 1_000_000:.2f}M"
        elif abs(num) >= 1_000:
            return f"${num / 1_000:.2f}K"
        else:
            return f"${num:.2f}"
    except Exception:
        return str(value)


def get_competitor_metrics(ticker_symbol):
    """
    Fetch and format key financial metrics for a single ticker.
    Returns a metrics dict, or None on failure.
    """
    try:
        info = yf.Ticker(ticker_symbol).info
        if not info or len(info) < 5:
            return None

        market_cap = info.get('marketCap', 'N/A')
        revenue = info.get('totalRevenue', info.get('revenue', 'N/A'))
        profit_margin = info.get('profitMargins', 'N/A')
        current_price = info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))

        if profit_margin not in ('N/A', None):
            try:
                profit_margin_display = f"{float(profit_margin) * 100:.2f}%"
            except Exception:
                profit_margin_display = 'N/A'
        else:
            profit_margin_display = 'N/A'

        return {
            'Company': info.get('longName', info.get('shortName', ticker_symbol)),
            'Ticker': ticker_symbol,
            'Market Cap': market_cap,
            'Market Cap Display': format_large_number(market_cap),
            'Revenue': revenue,
            'Revenue Display': format_large_number(revenue),
            'Profit Margin': profit_margin_display,
            'P/E Ratio': info.get('trailingPE', info.get('forwardPE', 'N/A')),
            'EPS': info.get('trailingEps', 'N/A'),
            'Dividend Yield': f"{float(info.get('dividendYield', 0)) * 100:.2f}%" if info.get('dividendYield') else 'N/A',
            'Beta': info.get('beta', 'N/A'),
            '52W High': f"${float(info.get('fiftyTwoWeekHigh', current_price)):.2f}" if current_price != 'N/A' else 'N/A',
            '52W Low': f"${float(info.get('fiftyTwoWeekLow', current_price)):.2f}" if current_price != 'N/A' else 'N/A',
            'Current Price': f"${float(current_price):.2f}" if current_price != 'N/A' else 'N/A',
        }
    except Exception as e:
        print(f"Error fetching metrics for {ticker_symbol}: {e}")
        return None


def compare_competitors(ticker_list):
    """
    Fetch metrics for a list of tickers with rate-limit protection.
    Returns: (DataFrame | None, list of failed tickers)
    """
    comparison_data = []
    failed_tickers = []

    for idx, ticker in enumerate(ticker_list):
        if idx > 0:
            time.sleep(0.5)
        metrics = get_competitor_metrics(ticker)
        if metrics:
            comparison_data.append(metrics)
        else:
            failed_tickers.append(ticker)

    if comparison_data:
        return pd.DataFrame(comparison_data), failed_tickers
    return None, ticker_list


def get_detailed_ticker_info(symbol):
    """
    Get comprehensive data for a single symbol.
    Works with stocks, indices, ETFs, forex, commodities, crypto.
    Returns: (detailed_info dict, history DataFrame, raw info dict)
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history(period="1y")

        if symbol.startswith('^'):
            asset_type = "Index"
        elif symbol.endswith('=X'):
            asset_type = "Forex"
        elif symbol.endswith('=F'):
            asset_type = "Commodity/Future"
        elif symbol.endswith('-USD'):
            asset_type = "Cryptocurrency"
        elif info.get('quoteType') == 'ETF':
            asset_type = "ETF"
        else:
            asset_type = "Stock"

        current_price = info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))

        detailed_info = {
            'Symbol': symbol,
            'Name': info.get('longName', info.get('shortName', symbol)),
            'Type': asset_type,
            'Current Price': current_price,
            'Currency': info.get('currency', 'USD'),
            'Market Cap': info.get('marketCap', 'N/A'),
            'Volume': info.get('volume', info.get('regularMarketVolume', 'N/A')),
            '52 Week High': info.get('fiftyTwoWeekHigh', 'N/A'),
            '52 Week Low': info.get('fiftyTwoWeekLow', 'N/A'),
            'Day High': info.get('dayHigh', 'N/A'),
            'Day Low': info.get('dayLow', 'N/A'),
            'Open': info.get('open', info.get('regularMarketOpen', 'N/A')),
            'Previous Close': info.get('previousClose', info.get('regularMarketPreviousClose', 'N/A')),
        }

        if asset_type == "Stock":
            detailed_info.update({
                'P/E Ratio': info.get('trailingPE', info.get('forwardPE', 'N/A')),
                'EPS': info.get('trailingEps', 'N/A'),
                'Dividend Yield': info.get('dividendYield', 'N/A'),
                'Beta': info.get('beta', 'N/A'),
                'Profit Margin': info.get('profitMargins', 'N/A'),
                'Revenue': info.get('totalRevenue', 'N/A'),
                'Sector': info.get('sector', 'N/A'),
                'Industry': info.get('industry', 'N/A'),
            })

        if not hist.empty:
            ytd_change = ((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
            detailed_info['YTD Change %'] = f"{ytd_change:.2f}%"

        return detailed_info, hist, info

    except Exception:
        return None, None, None


# ==================== CHARTS ====================

_CHART_LAYOUT = dict(
    plot_bgcolor='rgba(15, 23, 42, 0.3)',
    paper_bgcolor='rgba(15, 23, 42, 0)',
    font={'family': 'IBM Plex Sans, sans-serif', 'color': '#E2E8F0', 'size': 11},
    height=400,
    legend=dict(
        font={'size': 10},
        bgcolor='rgba(30, 41, 59, 0.6)',
        bordercolor='rgba(59, 130, 246, 0.2)',
        borderwidth=1,
    ),
    xaxis={'gridcolor': 'rgba(59, 130, 246, 0.08)', 'linecolor': 'rgba(59, 130, 246, 0.2)'},
    yaxis={'gridcolor': 'rgba(59, 130, 246, 0.08)', 'linecolor': 'rgba(59, 130, 246, 0.2)'},
)


def create_single_ticker_chart(symbol, hist):
    """Candlestick + volume chart for a single ticker."""
    if hist is None or hist.empty:
        return None

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=hist.index, open=hist['Open'], high=hist['High'],
        low=hist['Low'], close=hist['Close'], name=symbol,
    ))
    fig.add_trace(go.Bar(
        x=hist.index, y=hist['Volume'], name='Volume',
        yaxis='y2', opacity=0.3, marker=dict(color='#60A5FA'),
    ))

    layout = dict(
        title=f'{symbol} Price History (1Y)',
        yaxis=dict(title='Price'),
        yaxis2=dict(title='Volume', overlaying='y', side='right'),
        xaxis=dict(title='Date'),
        hovermode='x unified',
        showlegend=True,
        xaxis_rangeslider_visible=False,
    )
    layout.update(_CHART_LAYOUT)
    fig.update_layout(**layout)
    return fig


def create_competitor_stock_chart(ticker_list, period="1y"):
    """Normalized % performance comparison chart for multiple tickers."""
    fig = go.Figure()

    for ticker in ticker_list:
        try:
            data = yf.Ticker(ticker).history(period=period)
            if not data.empty:
                normalized = (data['Close'] / data['Close'].iloc[0] - 1) * 100
                fig.add_trace(go.Scatter(
                    x=data.index, y=normalized, mode='lines', name=ticker,
                    line=dict(width=2.5),
                    hovertemplate='<b>%{fullData.name}</b><br>Date: %{x}<br>Change: %{y:.2f}%<extra></extra>',
                ))
        except Exception:
            continue

    layout = dict(
        title='Stock Performance Comparison (Normalized)',
        xaxis_title='Date',
        yaxis_title='% Change from Start',
        hovermode='x unified',
        showlegend=True,
    )
    layout.update(_CHART_LAYOUT)
    fig.update_layout(**layout)
    return fig


def create_competitor_metrics_chart(df, metric):
    """Bar chart comparing a single metric across multiple companies."""
    if df is None or df.empty or metric not in df.columns:
        return None

    df_filtered = df[df[metric] != 'N/A'].copy()
    if df_filtered.empty:
        return None

    if metric in ('Market Cap', 'Revenue'):
        df_filtered[metric] = pd.to_numeric(df_filtered[metric], errors='coerce')
        df_filtered = df_filtered.dropna(subset=[metric])

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_filtered['Company'],
        y=df_filtered[metric],
        marker=dict(color='#3B82F6', line=dict(width=0)),
        hovertemplate=f'<b>%{{x}}</b><br>{metric}: %{{y:,.2f}}<extra></extra>',
    ))

    layout = dict(
        title=f'Competitor Comparison: {metric}',
        xaxis_title='Company',
        yaxis_title=metric,
        showlegend=False,
    )
    layout.update(_CHART_LAYOUT)
    fig.update_layout(**layout)
    return fig


# ==================== ANALYSIS ORCHESTRATION ====================

def generate_market_data_analysis(question, symbols, query_type):
    """
    Main entry point: fetch data and generate an AI summary for the given symbols.

    Returns a result dict with keys:
        success, summary, data, analysis_type,
        and chart keys depending on analysis_type.
    """
    if not symbols and query_type != "general":
        return {
            'success': False,
            'message': 'Please specify ticker symbols (e.g., AAPL, ^GSPC, BTC-USD, EURUSD=X)',
        }

    try:
        # ── Single ticker ──────────────────────────────────────────────────
        if query_type == "single" and len(symbols) == 1:
            symbol = symbols[0]
            detailed_info, hist, _ = get_detailed_ticker_info(symbol)

            if detailed_info is None:
                return {'success': False, 'message': f'Could not fetch data for {symbol}.'}

            df = pd.DataFrame([detailed_info])
            price_chart = create_single_ticker_chart(symbol, hist)

            summary_prompt = f"""
You are CLIO, a financial analyst providing market analysis.
User Question: {question}
Asset: {symbol}
Data:
{df.to_string(index=False)}

Provide a concise 2-3 sentence analysis covering:
- Current status and recent performance
- Key metrics and what they indicate
- Notable strengths or concerns
Be specific with numbers.
"""
            response = st.session_state._genai_client.models.generate_content(
                model="gemini-2.5-flash", contents=summary_prompt
            )

            return {
                'success': True,
                'summary': response.text,
                'data': df,
                'analysis_type': 'single',
                'price_chart': price_chart,
                'symbol': symbol,
            }

        # ── Comparison (2+ tickers) ────────────────────────────────────────
        elif query_type == "comparison" or len(symbols) >= 2:
            comparison_df, failed_tickers = compare_competitors(symbols)

            if comparison_df is None or comparison_df.empty:
                return {
                    'success': False,
                    'message': f'Could not fetch data for: {", ".join(symbols)}',
                }

            status_msg = f"\n\n⚠️ Note: Could not fetch data for: {', '.join(failed_tickers)}" if failed_tickers else ""
            stock_chart = create_competitor_stock_chart(symbols)

            question_lower = question.lower()
            if 'market cap' in question_lower or 'size' in question_lower:
                metric, metric_chart = 'Market Cap', create_competitor_metrics_chart(comparison_df, 'Market Cap')
            elif 'revenue' in question_lower or 'sales' in question_lower:
                metric, metric_chart = 'Revenue', create_competitor_metrics_chart(comparison_df, 'Revenue')
            elif 'profit' in question_lower or 'margin' in question_lower:
                metric, metric_chart = 'Profit Margin', create_competitor_metrics_chart(comparison_df, 'Profit Margin')
            elif 'p/e' in question_lower or 'valuation' in question_lower:
                metric, metric_chart = 'P/E Ratio', create_competitor_metrics_chart(comparison_df, 'P/E Ratio')
            else:
                metric, metric_chart = 'Market Cap', create_competitor_metrics_chart(comparison_df, 'Market Cap')

            successful_symbols = comparison_df['Ticker'].tolist()

            summary_prompt = f"""
You are CLIO, a financial analyst providing market comparison analysis.
User Question: {question}
Requested Symbols: {', '.join(symbols)}
Successfully Analyzed: {', '.join(successful_symbols)}
Complete Data:
{comparison_df.to_string(index=False)}

Instructions:
1. Analyze ALL assets in the data (not just one)
2. Compare key metrics across all assets
3. Highlight significant differences and similarities
4. Provide specific numbers for each asset
5. Be concise (3-4 sentences)
"""
            response = st.session_state._genai_client.models.generate_content(
                model="gemini-2.5-flash", contents=summary_prompt
            )

            return {
                'success': True,
                'summary': response.text + status_msg,
                'data': comparison_df,
                'analysis_type': 'comparison',
                'stock_chart': stock_chart,
                'metric_chart': metric_chart,
                'focus_metric': metric,
                'symbols': successful_symbols,
                'failed_symbols': failed_tickers,
            }

        else:
            return {
                'success': False,
                'message': 'Please specify ticker symbols. Examples: AAPL, ^GSPC, BTC-USD, EURUSD=X',
            }

    except Exception as e:
        return {'success': False, 'message': f'Error analyzing market data: {str(e)}'}
