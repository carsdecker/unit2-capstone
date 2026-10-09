# test_reviewer.py — Silver check for validation/reviewer.py (5 Gemini calls).
# Feeds the reviewer answers from earlier testing whose correctness we already know,
# with the same sources the agents saw (retrieval is deterministic, so [Source N] lines up).
from agents import qualitative
from validation.reviewer import review, build_context

EMPLOYEE_Q = ("How does our employee satisfaction compare to industry standards "
              "and what policies might impact this?")
emp_chunks = qualitative.retrieve(EMPLOYEE_Q)
pw_chunks = qualitative.retrieve("How long must passwords be?")

# Data answers exactly as the quantitative agent produced them (Step 9 / Step 10 runs).
dept_data = ("Culinary has the highest average satisfaction score at approximately 4.23, "
             "followed by Engineering at 4.04, Marketing at 3.96, Sales at 3.81, Customer Care at 3.69, "
             "and Finance at 3.64. Operations has the lowest average satisfaction score at 3.36.")
overall_data = "The average employee satisfaction score is 3.77 (out of 5)."

# (label, answer, context, should_be_flagged)
cases = [
    ("1. Correct qualitative answer (Step 4)",
     "Passwords must be at least 14 characters long [Source 2].",
     build_context(pw_chunks), False),
    ("2. Wrong fact WITH citation (validator case E, passed validator.py)",
     "Passwords must be at least 8 characters long [Source 2].",
     build_context(pw_chunks), True),
    ("3. Synthesis v2: 4.0 and 3.7 comparison errors (passed validator.py)",
     "Culinary, Engineering, Marketing, Sales, Customer Care, and Finance are above Spoonful's "
     "target of 4.0 in most departments [Source 1], though Culinary and Engineering are the only "
     "ones strictly above 4.0. Operations (3.36) is below the target of 4.0 [Source 1], and below "
     "the department action plan threshold of 3.5 [Source 1]. Comparing to industry standards, "
     "Culinary, Engineering, Marketing, Sales, Customer Care, and Finance are above the consumer "
     "technology and food delivery benchmark of 3.7 [Source 1].",
     build_context(emp_chunks, dept_data), True),
    ("4. Step 10 synthesis: '3.77 matches 3.7' (passed validator.py)",
     "The score of 3.77 is below the company's internal departmental target of at least 4.0 "
     "[Source 1]. The score of 3.77 matches the industry average for consumer technology and "
     "food delivery companies of Spoonful's size (3.7) [Source 1].",
     build_context(emp_chunks, overall_data), True),
    ("5. Correct comparison (false-alarm check)",
     "Spoonful's average employee satisfaction of 3.77 is above the 3.7 industry benchmark "
     "[Source 1] but below its own target of 4.0 [Source 1]. Operations (3.36) is below the "
     "3.5 action-plan threshold [Source 1].",
     build_context(emp_chunks, dept_data + " " + overall_data), False),
]

for label, answer, context, should_flag in cases:
    r = review(answer, context)
    status = "PASS" if r["flag"] == should_flag else "MISS"
    print(f"\n[{status}] {label}")
    print(f"  expected flag={should_flag}  got flag={r['flag']}")
    for claim in r["unsupported_claims"]:
        print(f"  - {claim}")
    print(f"  tokens: in={r['input_tokens']} out={r['output_tokens']} (of which thinking={r['thinking_tokens']})")
