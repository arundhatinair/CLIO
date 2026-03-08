import sqlite3
import streamlit as st
import pandas as pd


# ==================== CONNECTION ====================

@st.cache_resource
def get_db_connection(db_path="finance_data.db"):
    """Cached SQLite database connection."""
    return sqlite3.connect(db_path, check_same_thread=False)


def validate_database():
    """
    Check that the database file exists and contains at least one table.
    Calls st.stop() with a helpful message if validation fails.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        if not tables:
            st.error("⚠️ Database Error: No tables found in finance_data.db")
            st.info("""
            **Your database is empty. Please:**
            1. Check that `finance_data.db` contains your data
            2. Import your financial data into the database
            3. Verify table structure matches your data

            **To check your database, run:**
            ```bash
            python check_database.py
            ```
            """)
            st.stop()
    except Exception as e:
        st.error(f"⚠️ Database Connection Error: {e}")
        st.info("Make sure `finance_data.db` exists in the same directory as this script.")
        st.stop()


# ==================== SCHEMA ====================

def get_schema_info(_conn):
    """Return a formatted string describing all tables and their columns."""
    cursor = _conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    schema_info = ""
    for (table_name,) in tables:
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        schema_info += f"**{table_name}**: `{', '.join(column_names)}`\n"
    return schema_info


# ==================== QUERY EXECUTION ====================

def execute_sql_query(_conn, query):
    """
    Execute a SELECT query safely.
    Returns: (DataFrame, None) on success, (None, error_string) on failure.
    """
    try:
        if not query.strip().lower().startswith("select"):
            raise ValueError("Only SELECT queries are allowed.")
        df = pd.read_sql_query(query, _conn)
        return df, None
    except Exception as e:
        return None, f"Query execution error: {e}"


# ==================== SQL GENERATION ====================

def generate_sql_from_question(schema, question, retries=3):
    """
    Translate a natural-language question into a SQLite SELECT query.
    Uses self-healing: on failure, re-prompts Gemini with the error message.
    """
    base_prompt = f"""
You are CLIO, a senior data analyst and SQLite SQL expert.

Your task is to translate the user's natural-language question into ONE correct,
executable SQLite SELECT query using the database schema below.

Database schema:
{schema}

User question:
"{question}"

Reasoning principles (follow internally):
- Infer user intent, not just literal wording.
- Map implied business concepts to the most semantically appropriate columns.
  (e.g., "revenue" → total_amount / sales / price * quantity)
- Detect subtext such as:
  • comparisons (higher/lower, before/after, vs)
  • trends (growth, decline, change over time)
  • rankings (top, bottom, best, worst)
  • aggregation intent (total, average, share, rate)
  • time filters (recent, last quarter, year-over-year)
- When column names are not explicitly mentioned, infer them from meaning and usage.
- Prefer the simplest query that fully answers the question.

Hard constraints:
- Use ONLY tables and columns present in the schema.
- Do NOT invent or guess column or table names.
- SQLite-compatible syntax ONLY.
- SELECT statements ONLY.
- Include GROUP BY, ORDER BY, WHERE clauses only if logically required.
- Use explicit column names (avoid SELECT *) unless unavoidable.
- Do NOT include comments, explanations, markdown, or formatting.
- Return ONLY the SQL query.
"""

    sql = None
    last_error = None

    for attempt in range(retries):
        if last_error:
            prompt = f"""
{base_prompt}

The previous SQL query failed with this SQLite error:
"{last_error}"

Previous SQL:
{sql}

Fix the query so that it executes correctly AND still answers the user's question.
Return ONLY the corrected SQL.
"""
        else:
            prompt = base_prompt + "\nSQL:"

        response = st.session_state._genai_client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        sql = (
            response.text
            .strip()
            .replace("```sql", "")
            .replace("```", "")
            .strip()
        )

        if not sql.lower().startswith("select"):
            sql = "SELECT " + sql.lstrip()

        try:
            conn = get_db_connection()
            df, err = execute_sql_query(conn, sql)
            if err is None:
                return sql
            last_error = err
        except Exception as e:
            last_error = str(e)

    # Fallback: return first table limited to 1 row
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
        result = cursor.fetchone()
        if result:
            return f"SELECT * FROM {result[0]} LIMIT 1;"
    except Exception:
        pass

    return "SELECT 'Database error: No tables found' AS error;"


# ==================== RESULT SUMMARY ====================

def generate_summary_from_results(question, sql, df):
    """Generate a concise natural-language summary of SQL query results via Gemini."""
    if df.empty:
        return "No results found for this query."

    prompt = f"""
You are CLIO, a financial data analyst.

User question: "{question}"
SQL query executed: `{sql}`
Results (DataFrame):
{df.to_string()}

Provide a concise, insightful summary of the results in 2-3 sentences.
Focus on key findings, trends, or notable data points.
Be precise and professional.
"""
    response = st.session_state._genai_client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt
    )
    return response.text
