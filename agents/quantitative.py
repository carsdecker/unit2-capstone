# agents/quantitative.py
import sqlite3
from google import genai
from google.genai import types, errors
from dotenv import load_dotenv
load_dotenv()

# The SDK does NOT retry by default (one attempt only). Gemini returned frequent
# 503 "high demand" errors in testing, and a "both" query needs 5 calls to succeed
# in a row. Retry server errors up to 4 attempts with backoff (~1s, 2s, 4s).
# 429 (quota) is excluded: on the free tier it means the daily limit is used up,
# so retrying only adds delay.
client = genai.Client(http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(
    attempts=4,
    http_status_codes=[500, 502, 503, 504]
)))

# Schema context: the model can't see the database, so we describe the tables.
# Without this it would guess table/column names and write SQL that fails.
# Engine + date format: in live testing the model wrote EXTRACT(QUARTER FROM date),
# which is PostgreSQL/MySQL syntax and a syntax error in SQLite.
# "Not linked": asked about sales by customer industry, the model wrote
# JOIN sales s ON c.id = s.id, pairing customer #N with unrelated sales row #N. The SQL
# ran and produced plausible but meaningless revenue-by-industry figures.
SCHEMA_CONTEXT = """
Database engine: SQLite. Use SQLite syntax only (e.g. strftime(), not EXTRACT()).
Dates are stored as TEXT in 'YYYY-MM-DD' format.
The tables are not linked: no column connects sales to customers or employees, so never JOIN them.

Available tables:
- sales(id, region, product, revenue, date, units_sold)
- customers(id, name, industry, churn_date, satisfaction_score)
- employees(id, department, satisfaction_score, tenure_years)
"""

def validate_sql(query: str) -> dict:
    blocked = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]
    for word in blocked:
        if word in query.upper():
            return {"valid": False, "reason": f"Blocked keyword: {word}"}
    if not query.strip().upper().startswith("SELECT"):
        return {"valid": False, "reason": "Only SELECT queries are permitted"}
    return {"valid": True, "reason": "OK"}

def generate_sql(query: str) -> dict:
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        # Schema first so the model knows what exists before reading the task.
        # "Answer only the parts...": in testing, asked to compare against industry
        # standards (not in any table), the model pulled customer satisfaction in as a
        # stand-in benchmark. Unanswerable parts are left to the qualitative agent.
        # "Return ONLY the SQL query": the output is executed directly, so any
        # extra prose or explanation would make it invalid SQL.
        contents=f"{SCHEMA_CONTEXT}\n\nGenerate a SQL query for: {query}\n\nAnswer only the parts of the question these tables can answer; do not substitute unrelated columns for missing data.\n\nReturn ONLY the SQL query, nothing else.",
        config=types.GenerateContentConfig(
            # 256 is plenty for one query; a hard cap limits cost if the model rambles.
            max_output_tokens=256,
            # Thinking tokens count against max_output_tokens (see smoke_test.py).
            thinking_config=types.ThinkingConfig(thinking_level="minimal")
        )
    )
    sql = response.text.strip()
    # flash-lite wraps SQL in ```sql fences despite "Return ONLY the SQL query"
    # (seen in live testing), which made validate_sql block every query.
    # Strip them here so the validator checks the actual SQL.
    if sql.startswith("```"):
        sql = sql.strip("`").removeprefix("sql").strip()
    return {
        "sql": sql,
        "input_tokens": response.usage_metadata.prompt_token_count,
        "output_tokens": response.usage_metadata.candidates_token_count
    }

def run(query: str) -> dict:
    sql_result = generate_sql(query)
    sql = sql_result["sql"]
    validation = validate_sql(sql)

    if not validation["valid"]:
        return {
            "answer": f"Query blocked: {validation['reason']}",
            "sql": sql,
            "rows": [],
            "validation": "FAILED",
            "input_tokens": sql_result["input_tokens"],
            "output_tokens": sql_result["output_tokens"]
        }

    try:
        conn = sqlite3.connect("./data/database.sqlite")
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        conn.close()

        # Use the model to interpret the results
        interpretation = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            # Original question + the SQL + real rows: the model explains numbers the
            # database produced rather than inventing its own.
            # rows[:20]: caps how much data goes into the prompt (token cost).
            # "Describe only what these results show": in testing the model invented a
            # "transactions" explanation (Q4) and a list of company policies it has no
            # access to. "Under 150 words": answers ran to 345-512 tokens and one was
            # cut off mid-sentence at max_output_tokens; output is the costliest token.
            contents=f"The user asked: {query}\n\nSQL query used: {sql}\n\nResults:\nColumns: {cols}\nData: {rows[:20]}\n\nProvide a clear, concise interpretation of these results. Describe only what these results show. Do not speculate about causes or recommend policies. If the question asks for information not in these results, say so in one sentence. Keep it under 150 words.",
            config=types.GenerateContentConfig(
                max_output_tokens=512,
                thinking_config=types.ThinkingConfig(thinking_level="minimal")
            )
        )

        return {
            "answer": interpretation.text,
            "sql": sql,
            "columns": cols,
            "rows": rows,
            "validation": "PASSED",
            "input_tokens": sql_result["input_tokens"] + interpretation.usage_metadata.prompt_token_count,
            "output_tokens": sql_result["output_tokens"] + interpretation.usage_metadata.candidates_token_count
        }

    except errors.APIError:
        # A Gemini outage during the interpretation call was caught below and reported
        # as "Query execution failed" (status ERROR) even though the SQL ran fine.
        # Let model-service errors reach main.py's handler; keep the catch-all for SQL.
        raise
    except Exception as e:
        return {
            "answer": f"Query execution failed: {str(e)}",
            "sql": sql,
            "rows": [],
            "validation": "ERROR",
            "input_tokens": sql_result["input_tokens"],
            "output_tokens": sql_result["output_tokens"]
        }
