# validation/reviewer.py — Silver stretch goal: a second validation strategy.
# validator.py checks FORM (is a citation present?); this checks TRUTH: a second model
# call reads the sources and judges whether each claim in the answer is supported.
# Motivation from testing: "Passwords must be at least 8 characters [Source 2]" and
# "Customer Care (3.69) ... above the benchmark of 3.7 [Source 1]" both passed validator.py.
from google import genai
from google.genai import types
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()

# Same retry policy as the agents (SDK makes one attempt by default; see agents/*.py).
client = genai.Client(http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(
    attempts=4,
    http_status_codes=[500, 502, 503, 504]
)))

# Structured output: the model must reply in exactly this shape, so the code reads
# booleans instead of interpreting free text (which would bring back fragile string matching).
# "Show your work": a first version asked straight for supported: true/false and twice
# accepted "3.77 matches the industry average (3.7)". Each check now writes out the claim
# and the evidence (with the numbers side by side) BEFORE its verdict — fields are generated
# in this order — and the overall verdict is computed in code from every check.
class Check(BaseModel):
    claim: str
    evidence: str
    correct: bool

class Review(BaseModel):
    checks: list[Check]

# "You did not write the ANSWER": frames it as an independent check, not a defence of its own work.
# "CONTEXT only": same grounding rule as the agents — no general knowledge.
# One check per claim AND per comparison, numbers written in order ("3.69 < 3.7"): our
#   known failures were comparison errors (3.69 called "above" 3.7; 3.77 said to "match" 3.7).
# Refusals count as supported: refusing is the correct behaviour when the answer is absent.
# Labelled DOCUMENT/DATA sources + "never list text from the CONTEXT": in the first test the
# unlabelled data block was itself flagged as an "unsupported claim", and correct comparisons
# using those numbers were flagged too.
REVIEWER_PROMPT = """You are a strict fact-checker. You did not write the ANSWER.
The CONTEXT contains DOCUMENT SOURCES and may contain a DATA SOURCE (database query results). Treat everything in the CONTEXT as true.
Check only the claims in the ANSWER; never list text that appears in the CONTEXT.
Check every factual claim in the ANSWER against the CONTEXT only.
A claim is supported only if the CONTEXT states it, or it follows from numbers in the CONTEXT by correct arithmetic or comparison.
For EACH factual claim and EACH comparison in the ANSWER, add one check:
- claim: the claim, quoted briefly
- evidence: what the CONTEXT says, with the exact numbers; for comparisons write the numbers in order, e.g. "3.69 < 3.7"
- correct: true only if the evidence supports the claim exactly
A refusal such as "I cannot find this information" is correct."""

def build_context(chunks: list[dict], data: str = None) -> str:
    """Labelled evidence for the reviewer. Chunks keep the same [Source N] numbering the
    agent saw, so citations line up; database results get their own labelled section."""
    context = "DOCUMENT SOURCES:\n"
    context += "".join(f"[Source {i+1}: {c['source']}]\n{c['content']}\n\n" for i, c in enumerate(chunks))
    if data:
        context += f"DATA SOURCE (database query results):\n{data}\n"
    return context

def review(answer: str, context: str) -> dict:
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=f"CONTEXT:\n{context}\n\nANSWER TO CHECK:\n{answer}",
        config=types.GenerateContentConfig(
            system_instruction=REVIEWER_PROMPT,
            response_mime_type="application/json",
            response_schema=Review,
            # One check per claim (~30-50 tokens each); a cut-off JSON would be unparseable
            # (→ fail closed → flagged), so leave generous headroom.
            max_output_tokens=2048,
            # thinking_level="low" was tried to fix comparison errors but produced 0 thinking
            # tokens on flash-lite (no effect), so the visible checks above do that job instead.
            thinking_config=types.ThinkingConfig(thinking_level="minimal")
        )
    )
    # Thinking is billed as output but is NOT included in candidates_token_count, so add it
    # or the tokenomics log would undercount if thinking ever occurs.
    thinking_tokens = response.usage_metadata.thoughts_token_count or 0
    result = response.parsed
    if result is None:
        # Fail closed: an unreadable review (e.g. JSON cut off at the token cap) must
        # never look like a pass.
        supported, claims = False, ["Reviewer response could not be parsed"]
    else:
        # Verdict computed in code: supported only if every individual check is correct.
        failed = [c for c in result.checks if not c.correct]
        supported = not failed
        claims = [f"{c.claim}  (evidence: {c.evidence})" for c in failed]
    return {
        "supported": supported,
        "unsupported_claims": claims,
        "flag": not supported,
        "warning": "Reviewer found claims not supported by the sources" if not supported else None,
        "input_tokens": response.usage_metadata.prompt_token_count,
        "output_tokens": response.usage_metadata.candidates_token_count + thinking_tokens,
        "thinking_tokens": thinking_tokens
    }
