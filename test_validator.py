# test_validator.py — Step 6 check for validation/validator.py
#   python test_validator.py          -> Parts 1-3 (free, no Gemini calls)
#   python test_validator.py --live   -> also Part 4 (1 Gemini call)
import sys
from validation.validator import validate_qualitative, validate_quantitative

# The 5 chunks retrieved for "How long must passwords be?" (Step 4). The validator
# only reads each chunk's "source", so the content can be left empty here.
chunks = [{"source": s, "chunk": c, "content": ""} for s, c in [
    ("security_policy.txt", 1), ("security_policy.txt", 0), ("code_review_process.txt", 0),
    ("customer_success_strategy.txt", 0), ("customer_complaints_handling.txt", 0)]]

def show(label, result):
    print(f"\n{label}")
    for key, value in result.items():
        print(f"    {key}: {value}")

# ---- Part 1: qualitative validator on real and constructed answers (free) ----
print("=" * 70, "\nPART 1: validate_qualitative")
qual_cases = [
    ("A. Real good answer (Step 4)",
     "Based on the Information Security Policy, passwords must be at least 14 characters long [Source 2]."),
    ("B. Real clean refusal (Step 4)",
     "I cannot find this information in the provided documents."),
    ("C. Real refusal that cited all 5 sources (Step 4 injection test)",
     "I cannot find this information in the provided documents. [Source 1, Source 2, Source 3, Source 4, Source 5]"),
    ("D. Constructed: wrong fact, no citation",
     "Passwords must be at least 8 characters long."),
    ("E. Constructed: wrong fact WITH a citation",
     "Passwords must be at least 8 characters long [Source 2]."),
    ("F. Constructed: correct answer, different citation wording",
     "Passwords must be at least 14 characters long (Sources 1 and 2)."),
]
for label, answer in qual_cases:
    print(f"\n  answer: {answer}")
    show(f"  {label}", validate_qualitative(answer, chunks))

# ---- Part 2: quantitative validator on real outputs (free) ----
print("\n" + "=" * 70, "\nPART 2: validate_quantitative")
quant_cases = [
    ("G. Real churn answer (Step 5)", "Your customer churn rate is **18.33%**.", "PASSED"),
    ("H. Real fenced-SQL block (Step 5, before fix)", "Query blocked: Only SELECT queries are permitted", "FAILED"),
    ("I. Real Q4 answer with the made-up 'Key Takeaway' (Step 5)",
     "...each region recording exactly 9 transactions. This indicates that the revenue gap in the West "
     "was driven by a lower average order value...", "PASSED"),
]
for label, answer, status in quant_cases:
    show(f"  {label}", validate_quantitative(answer, "", status))

# ---- Part 3: brief's checkpoint, quantitative: submit a non-SELECT query (free) ----
# Replace generate_sql so the "model" returns a DROP. No Gemini call is made.
print("\n" + "=" * 70, "\nPART 3: checkpoint: non-SELECT query through the real agent")
from agents import quantitative
quantitative.generate_sql = lambda q: {"sql": "DROP TABLE sales", "input_tokens": 0, "output_tokens": 0}
r = quantitative.run("Delete the sales table")
print(f"  agent answer: {r['answer']}")
show("  validate_quantitative", validate_quantitative(r["answer"], r["sql"], r["validation"]))

# ---- Part 4: brief's checkpoint, qualitative: irrelevant context (1 Gemini call) ----
if "--live" in sys.argv:
    print("\n" + "=" * 70, "\nPART 4: checkpoint: irrelevant context (live)")
    from agents import qualitative
    # Ask about passwords, but hand the model only chunks with NO security content.
    irrelevant = [c for c in qualitative.retrieve("refunds and discounts", top_k=7)
                  if c["source"] != "security_policy.txt"][:5]
    qualitative.retrieve = lambda q: irrelevant
    r = qualitative.run("How long must passwords be?")
    print(f"  chunks given: {[c['source'] for c in irrelevant]}")
    print(f"  answer: {r['answer']}")
    show("  validate_qualitative", validate_qualitative(r["answer"], r["chunks"]))
