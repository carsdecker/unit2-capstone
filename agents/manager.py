# agents/manager.py
from google import genai
from google.genai import types
from dotenv import load_dotenv
from agents import qualitative, quantitative
from validation.validator import validate_qualitative, validate_quantitative
from validation.reviewer import review, build_context
from tokenomics.logger import log
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

def classify(query: str) -> str:
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        # Closed label set + a one-line definition of each: the model picks from
        # three known options instead of inventing its own categories.
        # "one word only": keeps output to a single token so it can be compared
        # directly against the allowed labels below.
        contents=f"""Classify this query as exactly one of: qualitative, quantitative, both.

qualitative = questions about policies, processes, procedures, explanations, documentation
quantitative = questions about numbers, metrics, trends, comparisons, SQL-queryable data
both = questions that need both document search and data analysis

Query: {query}

Reply with one word only: qualitative, quantitative, or both.""",
        config=types.GenerateContentConfig(
            # One word needs only a few tokens; the cap keeps classification cheap.
            max_output_tokens=10,
            # Essential here: with thinking on, 10 tokens would be used up by thinking
            # and the reply would come back empty (see smoke_test.py).
            thinking_config=types.ThinkingConfig(thinking_level="minimal")
        )
    )
    route = response.text.strip().lower()
    log(query, "manager-classifier", response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count)
    return route if route in ["qualitative", "quantitative", "both"] else "qualitative"

# Synthesis prompt: the brief's architecture has the manager synthesise the final
# response, but its code printed the two agent answers separately. In testing, a
# "both" query got two half-answers and nothing connected them.
# "ONLY facts stated in the two answers": the synthesiser sees no documents or data,
# so anything else would come from general knowledge.
# Numbers from DATA, policies from DOCUMENTS: each agent is only trusted for what it
# can actually see (the data agent once invented company policies).
# Keep [Source N] citations: lets validate_qualitative check the synthesis too.
# Revision after first live run: the model placed 3.77 and the 3.7 benchmark in
# separate paragraphs without ever comparing them, then repeated the whole policy
# list. "Direct answer first" + "Comparing those facts is allowed" make it connect
# the two answers; "most relevant policies" stops it copying the document answer.
SYNTHESIS_PROMPT = """You combine two answers to the same question into one answer.
Start with a direct answer to the question.
Where numbers in the DATA ANSWER relate to targets, thresholds or benchmarks in the DOCUMENT ANSWER, compare them explicitly and say whether each is above or below.
Use ONLY facts stated in the two answers; add nothing from general knowledge. Comparing those facts is allowed.
Take numbers only from the DATA ANSWER. Take policies, targets and benchmarks only from the DOCUMENT ANSWER.
Mention only the policies most relevant to the question; do not repeat every policy listed.
Keep the [Source N] citations from the DOCUMENT ANSWER for any document facts you use.
If the two answers do not cover part of the question, say so.
Keep it under 150 words."""

def synthesise(query: str, qual_answer: str, quant_answer: str) -> dict:
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        # Labelled sections so the model can tell which facts came from which agent.
        contents=f"QUESTION: {query}\n\nDOCUMENT ANSWER (from company policy documents):\n{qual_answer}\n\nDATA ANSWER (from the company database):\n{quant_answer}\n\nCOMBINED ANSWER:",
        config=types.GenerateContentConfig(
            system_instruction=SYNTHESIS_PROMPT,
            # ~200 words is ~270 tokens; 400 leaves headroom without inviting rambling.
            max_output_tokens=400,
            thinking_config=types.ThinkingConfig(thinking_level="minimal")
        )
    )
    return {
        "answer": response.text,
        "input_tokens": response.usage_metadata.prompt_token_count,
        "output_tokens": response.usage_metadata.candidates_token_count
    }

def run_review(query: str, answer: str, context: str):
    """Silver: second validation strategy. A reviewer call checks each claim in the answer
    against its sources; validator.py only checks that citations are present."""
    result = review(answer, context)
    log(query, "reviewer", result["input_tokens"], result["output_tokens"])
    if result["flag"]:
        print(f"\n⚠️  REVIEWER WARNING: {result['warning']}")
        for claim in result["unsupported_claims"]:
            print(f"   - {claim}")
    else:
        print("\n✅ Reviewer: every claim is supported by the sources")

def run(query: str):
    print(f"\nQuery: {query}")
    route = classify(query)
    print(f"Route: {route}")

    qual_result = None
    quant_result = None

    if route in ["qualitative", "both"]:
        qual_result = qualitative.run(query)
        validation = validate_qualitative(qual_result["answer"], qual_result["chunks"])
        log(query, "qualitative", qual_result["input_tokens"], qual_result["output_tokens"])
        if validation["flag"]:
            print(f"\n⚠️  VALIDATION WARNING: {validation['warning']}")
        # Qualitative-only: this IS the final answer, so review it before printing.
        # ("both" queries review the synthesis instead — one review per query.)
        if route == "qualitative":
            run_review(query, qual_result["answer"], build_context(qual_result["chunks"]))
        print(f"\n[Qualitative]\n{qual_result['answer']}")

    if route in ["quantitative", "both"]:
        quant_result = quantitative.run(query)
        validation = validate_quantitative(
            quant_result["answer"],
            quant_result["sql"],
            quant_result["validation"]
        )
        log(query, "quantitative", quant_result["input_tokens"], quant_result["output_tokens"])
        if validation["flag"]:
            print(f"\n⚠️  VALIDATION WARNING: {validation['warning']}")
        print(f"\n[Quantitative]\n{quant_result['answer']}")
        print(f"SQL used: {quant_result['sql']}")

    # Synthesis: only when both agents produced a usable answer. If the SQL was
    # blocked or errored there is no data to combine, so the two parts stand alone.
    if route == "both" and quant_result["validation"] == "PASSED":
        synth = synthesise(query, qual_result["answer"], quant_result["answer"])
        # Every model response passes validation: reuse the qualitative check, since
        # the synthesis must carry the document citations through.
        validation = validate_qualitative(synth["answer"], qual_result["chunks"])
        log(query, "manager-synthesis", synth["input_tokens"], synth["output_tokens"])
        if validation["flag"]:
            print(f"\n⚠️  VALIDATION WARNING: {validation['warning']}")
        # Review the synthesis (the answer the user relies on) against the document chunks
        # AND the data answer it was built from — where the comparison errors happened.
        run_review(query, synth["answer"], build_context(qual_result["chunks"], quant_result["answer"]))
        print(f"\n[Synthesised Answer]\n{synth['answer']}")
    elif route == "both":
        # No synthesis (SQL blocked/errored): the document answer is the usable answer, so
        # review it. It has already printed above, so the verdict follows it here.
        run_review(query, qual_result["answer"], build_context(qual_result["chunks"]))
