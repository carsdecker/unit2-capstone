# test_manager.py — Step 8 check for agents/manager.py
#   python test_manager.py          -> Part 1 only (free, fake model replies)
#   python test_manager.py --live   -> also Part 2 (1 Gemini call per query)
import os
import sys
import tempfile
from types import SimpleNamespace
from agents import manager

# classify() writes to tokenomics_log.jsonl; keep test entries out of the real log.
os.chdir(tempfile.mkdtemp())

# ---- Part 1: how classify() parses replies (free) ----
def fake_reply(text):
    """Stand-in for client.models.generate_content that returns a chosen reply."""
    usage = SimpleNamespace(prompt_token_count=0, candidates_token_count=0)
    return lambda **kwargs: SimpleNamespace(text=text, usage_metadata=usage)

real_generate = manager.client.models.generate_content
# (fake model reply, route we'd want)
cases = [
    ("qualitative",   "qualitative"),
    ("Quantitative",  "quantitative"),   # capital letter
    (" both\n",       "both"),           # stray whitespace
    ("Quantitative.", "quantitative"),   # trailing full stop
    ("banana",        "qualitative"),    # nonsense -> brief's default
    (None,            "qualitative"),    # empty reply (what thinking caused in Step 2)
]
print("PART 1: classify() parsing")
for reply, wanted in cases:
    manager.client.models.generate_content = fake_reply(reply)
    try:
        got = manager.classify("test query")
        status = "PASS" if got == wanted else "MISMATCH"
        print(f"  [{status}] reply={reply!r:16} -> route={got!r} (wanted {wanted!r})")
    except Exception as e:
        print(f"  [CRASH]    reply={reply!r:16} -> {type(e).__name__}: {e}")
manager.client.models.generate_content = real_generate

# ---- Part 2: real classifications (costs quota) ----
if "--live" in sys.argv:
    tests = [
        ("What is our company's security policy?", "qualitative"),
        ("Explain the code review process", "qualitative"),
        ("Show me monthly revenue trends", "quantitative"),
        ("What is our customer churn rate?", "quantitative"),
        ("How does our employee satisfaction compare to industry standards "
         "and what policies might impact this?", "both"),
    ]
    print("\nPART 2: real classifications")
    for query, expected in tests:
        route = manager.classify(query)
        status = "PASS" if route == expected else "CHECK"
        print(f"  [{status}] {route!r:15} (expected {expected!r}) <- {query}")
