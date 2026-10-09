# test_logger.py — Step 7 check for tokenomics/logger.py (free, no Gemini calls)
import os
import tempfile
from tokenomics.logger import log

# log() appends to tokenomics_log.jsonl in the current folder. That file is a
# deliverable, so run this test inside a throwaway temp folder instead.
os.chdir(tempfile.mkdtemp())

# Real token counts from Steps 4 and 5, with costs worked out by hand:
#   (tokens_in / 1000 * 0.0003) + (tokens_out / 1000 * 0.0025)
tests = [
    ("How long must passwords be?",           "qualitative",  2739,  22, 0.000877),
    ("What is our customer churn rate?",      "quantitative",  227,  91, 0.000296),
    ("Compare Q4 performance across regions", "quantitative",  342, 345, 0.000965),
]

for query, agent, tokens_in, tokens_out, expected in tests:
    entry = log(query, agent, tokens_in, tokens_out)
    status = "PASS" if entry["cost_usd"] == expected else "MISMATCH"
    print(f"  [{status}] cost_usd={entry['cost_usd']} (expected {expected}) | "
          f"per 1,000 queries: ${entry['cost_per_1000_queries']}")

with open("tokenomics_log.jsonl") as f:
    lines = f.readlines()
print(f"\nLog file has {len(lines)} lines. First line:\n{lines[0]}")
