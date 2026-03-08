# CLIO — Financial Data Intelligence

A Streamlit application for financial data analysis with three modes:
- **Internal Database** — Natural language SQL queries over your SQLite database
- **Market Data** — Live stock, crypto, forex, ETF, and commodity analysis via Yahoo Finance
- **PDF Analysis** — RAG-powered chat with financial report PDFs, with citation highlighting

## Project Structure

```
clio/
├── app.py                  ← Entry point (routing + session state only)
├── modules/
│   ├── styles.py           ← All CSS + header renderer
│   ├── database.py         ← SQLite connection, schema, SQL generation, summaries
│   ├── market.py           ← yfinance fetching, ticker detection, charts, analysis
│   ├── visualization.py    ← Chart type detection, building, and Streamlit rendering
│   ├── pdf_analysis.py     ← RAG indexing, chat pipeline, page renderer
│   └── report.py           ← PDF export with ReportLab
├── requirements.txt
├── .env.example
└── .streamlit/
    └── config.toml
```

## Setup

```bash
git clone <your-repo-url>
cd clio
pip install -r requirements.txt
cp .env.example .env   # add your Google API key
streamlit run app.py
```

## Deploying to Streamlit Cloud

1. Push this repo to GitHub (without `.env` and `finance_data.db`)
2. Connect at [share.streamlit.io](https://share.streamlit.io)
3. In **Advanced settings → Secrets**, add:
   ```toml
   GOOGLE_API_KEY = "your_google_api_key_here"
   ```
4. For the database, either include `finance_data.db` in the repo or connect to a cloud DB

## Environment Variables

| Variable | Description |
|---|---|
| `GOOGLE_API_KEY` | Google Gemini API key (required) |
