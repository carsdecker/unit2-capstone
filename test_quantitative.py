# test_quantitative.py — Step 5 check for agents/quantitative.py
#   python test_quantitative.py          -> Part 1 only (free, no Gemini calls)
#   python test_quantitative.py --live   -> also Part 2 (2 Gemini calls per query)
import sys
from agents import quantitative

# ---- Part 1: validate_sql (free) ----
# (sql, should_be_valid, why we're testing it)
cases = [
    ("SELECT region, SUM(revenue) FROM sales GROUP BY region", True,  "normal read query"),
    ("DROP TABLE sales",                                       False, "destructive"),
    ("DELETE FROM customers",                                  False, "destructive"),
    ("UPDATE employees SET satisfaction_score = 5",            False, "modifies data"),
    ("SELECT * FROM sales; DROP TABLE sales",                  False, "SELECT hiding a DROP"),
    ("PRAGMA table_info(sales)",                               False, "not a SELECT"),
    ("```sql\nSELECT COUNT(*) FROM customers\n```",            True,  "markdown fences (common model output)"),
    ("WITH q4 AS (SELECT * FROM sales) SELECT * FROM q4",      True,  "CTE: a legitimate read query"),
    ("SELECT churn_date AS last_update FROM customers",        True,  "harmless word containing UPDATE"),
]

print("PART 1: validate_sql")
for sql, expected, why in cases:
    result = quantitative.validate_sql(sql)
    ok = "PASS" if result["valid"] == expected else "MISMATCH"
    print(f"  [{ok}] expected valid={expected!s:5}  got valid={result['valid']!s:5}  ({why}) -> {result['reason']}")

# ---- Part 2: full agent (costs quota) ----
if "--live" in sys.argv:
    # Expected answers come from the answer key in generate_data.py's output.
    live_tests = [
        ("What is our customer churn rate?", "18.3"),
        ("Compare Q4 performance across regions", "West"),
    ]
    print("\nPART 2: full agent")
    for query, expected in live_tests:
        r = quantitative.run(query)
        status = "PASS" if expected in r["answer"] else "CHECK"
        print(f"\n[{status}] {query}   (expected to mention {expected!r})")
        print(f"  validation: {r['validation']}")
        print(f"  SQL: {r['sql']}")
        print(f"  rows: {r['rows'][:5]}")
        print(f"  answer: {r['answer']}")
        print(f"  tokens: in={r['input_tokens']} out={r['output_tokens']}")
