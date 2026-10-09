# Unit 2 Capstone: Multi-Agent RAG System

A Python CLI that answers qualitative and quantitative questions about **Spoonful**, a fictional
meal-kit company, using three coordinated agents, a two-layer validation system, and per-call
token cost logging.

**Tier reached:** 🥉 Bronze (all must-haves) · 🥈 Silver (reviewer validation) · 🥇 Gold (tokenomics optimisation)

> **Model note:** the brief specifies Claude (`claude-sonnet-4-6`). This build uses
> **Google Gemini (`gemini-3.5-flash-lite`)** via the `google-genai` SDK, following the course's
> move to Gemini. Every place the brief calls Claude is translated one-for-one; the architecture,
> prompts, validation and logging are otherwise as specified, with the evidence-driven changes
> listed under [Design decisions](#design-decisions-and-departures-from-the-brief).

---

## Architecture

```
User Query (CLI: main.py)
      │
      ▼
┌──────────────────────┐   1 call: classify → qualitative / quantitative / both
│    Manager Agent     │
└──────────────────────┘
      │                              │
      ▼                              ▼
┌───────────────────────┐    ┌────────────────────────┐
│  Qualitative Agent    │    │  Quantitative Agent     │
│  • ChromaDB vectors   │    │  • NL → SQL (Gemini)    │
│  • top-5 semantic     │    │  • strip fences         │
│    search (MiniLM)    │    │  • validate_sql ◄── blocks anything but SELECT
│  • Gemini answer with │    │  • SQLite (read)        │
│    [Source N] cites   │    │  • Gemini interprets    │
└───────────────────────┘    └────────────────────────┘
      │                              │
      └──────────────┬───────────────┘
                     ▼
      ┌──────────────────────────────┐  "both" only: combines the two answers
      │  Manager synthesis (Gemini)  │  (numbers from data, policies from documents)
      └──────────────────────────────┘
                     ▼
      ┌──────────────────────────────┐
      │  Validation layer            │
      │  1. validator.py  (rules)    │  citation present? refusal? SQL passed?
      │  2. reviewer.py   (Gemini)   │  is every claim supported by the sources?  ← Silver
      └──────────────────────────────┘
                     ▼
      ┌──────────────────────────────┐
      │  Tokenomics logger           │  tokens + cost per call → tokenomics_log.jsonl
      └──────────────────────────────┘
                     ▼
              Response to user
```

Model calls per query: **qualitative 3** (classify, answer, review) · **quantitative 3**
(classify, SQL, interpret) · **both 6** (classify, answer, SQL, interpret, synthesise, review).

---

## Project structure

```
unit2-capstone/
├── agents/
│   ├── manager.py          # classify, route, synthesise "both" answers, run reviewer
│   ├── qualitative.py      # ChromaDB retrieval + grounded, cited answers
│   └── quantitative.py     # NL→SQL, validate_sql, SQLite execution, interpretation
├── validation/
│   ├── validator.py        # rule-based checks (from the brief, unchanged)
│   └── reviewer.py         # Silver: model-based claim checking
├── tokenomics/
│   └── logger.py           # per-call token + cost logging
├── data/
│   ├── documents/          # 6 Spoonful policy documents (.txt)
│   ├── chroma/             # vector store (built by ingest.py)
│   └── database.sqlite     # sales / customers / employees (built by generate_data.py)
├── generate_data.py        # builds the practice database (seeded, reproducible)
├── ingest.py               # chunks + embeds documents into ChromaDB
├── main.py                 # CLI entry point
├── analyze_tokenomics.py   # summarises tokenomics_log.jsonl (no model calls)
├── smoke_test.py           # Step 2 connectivity check
├── test_*.py               # per-component test scripts (see Testing)
├── tokenomics_log.jsonl    # token/cost log from testing
├── requirements.txt
└── .env                    # GEMINI_API_KEY — never committed (.gitignore)
```

---

## Setup and usage

Requires Python 3.11+ (developed on 3.11.5; the course AWS WorkSpace runs **3.12.3**, which was
used for all logged testing with no compatibility issues).

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` in the project root (it is listed in `.gitignore`):

```
GEMINI_API_KEY=your_key_here
```

Build the data stores and check connectivity (run everything from the project root):

```bash
python generate_data.py     # → sales: 144 rows, customers: 60 rows, employees: 120 rows
python ingest.py            # → 7 chunks from 6 documents
python smoke_test.py        # → a one-sentence greeting + token counts
```

Run the CLI:

```bash
python main.py
```

```
Spoonful Enterprise RAG System
Type 'exit' to quit.

Ask a question: What is the refund approval limit for customer care agents?
```

### Data

No dataset was provided, so both data sources were created for this project:

- **Documents** (`data/documents/`): six policy documents written for Spoonful — security,
  code review, complaint handling, customer success strategy, employee wellbeing, sales and
  pricing. The brief permits "source your own". They contain specific, checkable facts
  (e.g. "passwords must be at least 14 characters", "agents may refund up to $50").
- **Database** (`generate_data.py`): seeded with `random.seed(42)`, so every machine builds an
  identical database and answers can be checked against a known key. The data is designed to
  line up with the documents:

| Fact | Database | Document |
|---|---|---|
| Customer churn | 18.3% | strategy: reduce churn from 18% to 14% |
| Avg customer satisfaction | 3.91 | strategy: raise from 3.9 to 4.2 |
| Avg employee satisfaction | 3.77 | wellbeing: industry benchmark 3.7 |
| Lowest department | Operations 3.36 | wellbeing: below 3.5 → action plan within 30 days |
| Q4 revenue by region | West lowest (141,006) | sales: >10% below target → recovery plan |

**Free-tier note:** development used a free-tier Gemini key ($0 actual spend). Google's terms
state free-tier content may be used to improve its products, which is acceptable only because
Spoonful's data is fictional — real company or client data should never be sent on a free-tier key.

---

## Supported query types

All brief queries were run through the CLI (outputs in `step10_output*.txt`) and checked by hand
against the answer key and the source documents.

| Query | Route | Result |
|---|---|---|
| What is our company's security policy? | qualitative | ✅ all facts correct, citations map to the right chunks |
| Explain the code review process | qualitative | ✅ |
| How do we handle customer complaints? | qualitative | ✅ |
| Show me monthly revenue trends | quantitative | ✅ all 12 months match the database |
| What is our customer churn rate? | quantitative | ✅ 18.33% |
| Compare Q4 performance across regions | quantitative | ✅ North > East > South > West |
| How does our employee satisfaction compare to industry standards and what policies might impact this? | both | ✅ final run (see Trust-but-Verify #3 for the earlier failures) |
| Analyse our sales performance and recommend policy changes based on our customer success strategies | both | ✅ after the JOIN fix (Trust-but-Verify #4) |
| What is the refund approval limit for customer care agents? | qualitative | ✅ $50 |
| Which department has the lowest employee satisfaction? | quantitative | ✅ Operations |
| How long must passwords be? | qualitative | ✅ 14 characters, reviewer ✅ |

For the sales query, the documents contain no policy *recommendations*, so the system says so
rather than inventing them: *"the provided sources do not contain quarterly revenue targets ...
or specific policy changes based on customer success strategies."* For a grounded system, that
refusal is the correct behaviour.

---

## Validation layer

Every model response passes through validation before it is shown.

**1. Rule-based (`validation/validator.py`, from the brief, unchanged)** — free and instant.
- Qualitative: is a `Source N` citation present? did the model refuse ("cannot find")?
  Flags uncited, non-refusal answers.
- Quantitative: did `validate_sql` pass, block, or error? Flags anything but PASSED.
- Brief checkpoints: a `DROP TABLE` pushed through the real agent is blocked and flagged;
  a password question given only irrelevant chunks returns the exact refusal sentence
  (`refused_to_answer: True` — nothing ungrounded reaches the user, so nothing to flag).

**Testing showed its limit: it checks form, not truth.** These all passed it:
`"Passwords must be at least 8 characters long [Source 2]"` (the policy says 14);
`"Customer Care [3.69] ... above the benchmark of 3.7 [Source 1]"`; an invented explanation of
correct SQL results. That motivated the second strategy.

**2. Model-based reviewer (`validation/reviewer.py`) — 🥈 Silver.** See [Silver](#-silver-reviewer-validation).

---

## Trust-but-Verify

Real examples from testing. Outputs are quoted from the logged runs.

### 1. Monthly revenue — accepted, and the model corrected my answer key

- **Query:** "Show me monthly revenue trends"
- **Returned:** all 12 monthly totals (185,169 → 244,658) and *"Aside from a slight dip in April
  and October, total revenue increases month-over-month."*
- **Flagged:** nothing (SQL PASSED).
- **Decision:** I checked every figure against the database — all correct. My own answer key
  only listed the October dip; the database confirms April too (Mar 203,505 → Apr 202,592).
  **Accepted unchanged.** Verification cuts both ways: the reference you check against needs
  checking too.

### 2. Q4 regions — correct numbers, invented explanation

- **Query:** "Compare Q4 performance across regions"
- **Returned (first version):** correct revenue for all four regions, then:
  *"each region recording exactly 9 transactions. This indicates that the revenue gap in the West
  was driven by a lower average order value ... rather than a lack of transaction frequency."*
- **Flagged:** nothing — `validate_quantitative` only checks that the SQL passed.
- **Why I didn't trust it:** `COUNT(id)` counts table rows, and the table has exactly one row per
  region × product × month (3 × 3 = 9 per region by construction) — not transactions. West's own
  row shows fewer units (6,358 vs ~8,700), contradicting the conclusion.
- **Decision:** kept the numbers; **changed the interpretation prompt** (Trust-but-Verify #3,
  Fix 1) to *"Describe only what these results show. Do not speculate about causes..."*. The
  re-run reported the same figures with no invented explanation.

### 3. Employee satisfaction ("both") — four failures in one answer, fixed in stages

- **Query:** "How does our employee satisfaction compare to industry standards and what
  policies might impact this?"
- **Returned (first run):**
  - SQL `(SELECT AVG(satisfaction_score) FROM customers) AS avg_customer_satisfaction` — used
    **customer** satisfaction as a stand-in "benchmark" for **employee** satisfaction.
  - A "Policies That Might Impact These Results" section (compensation, bonuses, *"inflexible
    shift policies"*) — the quantitative agent has no document access; the real policy gives
    Operations shift-preference scheduling and a shift-swap system.
  - Cut off mid-sentence (*"(e.g., Engineering vs. Culinary/Operations"*) at the token cap.
  - No synthesis: two separate half-answers; nobody connected the scores to the benchmarks.
- **Flagged:** nothing (SQL PASSED, document answer cited).
- **Changed:**
  - **Fix 1** (quantitative prompts): "answer only the parts these tables can answer; do not
    substitute unrelated columns" + "describe only what these results show ... under 150 words".
    Result: *"The provided data does not contain information regarding industry standards or
    company policies."* — 82% fewer output tokens (see Tokenomics).
  - **Fix 2:** a manager synthesis step (the brief's architecture says the manager
    "synthesises the final response"; its code printed two separate answers).
- **Accepted:** the document half throughout — every benchmark (3.7, 3.4, 4.0, 3.5) correct and cited.

### 4. Sales analysis — valid SQL, meaningless numbers

- **Query:** "Analyse our sales performance and recommend policy changes based on our customer
  success strategies"
- **Returned:** *"**Education:** Generates the highest total revenue ($203,696.00)..."* from
  ```sql
  FROM customers c JOIN sales s ON c.id = s.id
  ```
- **Flagged:** nothing — the SQL is valid, ran, and returned real values from the database.
- **Why I didn't trust it:** the `sales` table has no customer column. I re-ran the SQL: it
  paired customer #N with unrelated sales row #N (rows 1–60, Jan–May only). "Revenue by industry"
  was fiction, and the synthesis repeated it.
- **Changed:** schema context now states *"The tables are not linked: no column connects sales
  to customers or employees, so never JOIN them."* — a true fact about the data model, not a rule
  tuned to this question. Re-run: `FROM sales GROUP BY region, product`; all six figures quoted
  verified against the database.

### 5. ★ The output I did not immediately trust: confident, cited, and wrong

- **Query:** the employee-satisfaction question, after the synthesis prompt was revised to
  compare numbers explicitly.
- **Returned:**
  > *"Culinary, Engineering, Marketing, Sales, Customer Care, and Finance are **above** Spoonful's
  > target of 4.0 in most departments [Source 1], though Culinary and Engineering are the only ones
  > strictly above 4.0. ... Comparing to industry standards, Culinary, Engineering, Marketing,
  > Sales, **Customer Care, and Finance are above** the consumer technology and food delivery
  > benchmark of 3.7 [Source 1]."*
- **Flagged:** nothing — the answer was cited, so `validator.py` passed it.
- **Why I didn't trust it:** it contradicts itself on the 4.0 target, and checking each number
  by hand: Customer Care **3.69** and Finance **3.64** are *below* 3.7. It did correctly find the
  key insight — Operations (3.36) below the 3.5 action-plan threshold.
- **How I resolved it:** not with another prompt tweak (which risked over-fitting to one question)
  but with a **second validation strategy** — the Silver reviewer. Given this exact answer, it now
  returns: *"Customer Care is 3.69 which is not > 3.7"* and flags the answer.

### Other incidents (summary)

| Incident | Cause | Resolution |
|---|---|---|
| Smoke test returned `None` | Gemini 3 "thinks" by default; 44 of 50 tokens used thinking | `thinking_level="minimal"` on every call |
| Model wrapped SQL in ```` ```sql ```` → every query blocked | Ignored "Return ONLY the SQL query" | Strip fences in code before `validate_sql` (validator unchanged) |
| `EXTRACT(QUARTER FROM date)` → syntax error | Model assumed PostgreSQL | Schema context names SQLite + date format |
| 503 "high demand" crashed the CLI | No error handling; SDK does not retry by default | Retries (5xx, backoff) + `main.py` catches `APIError`, session continues |
| 503 reported as "Query execution failed" | Brief's `except Exception` wrapped the interpretation call | Re-raise `APIError` before the catch-all |
| Prompt injection: "Ignore all previous instructions..." | — | Refused (rules in `system_instruction`) |
| Retrieval: password rule at token 371 of a chunk | MiniLM embeds only the first 256 tokens | Kept chunk size 500 (top-5 of 7 chunks still retrieves it); documented as a scale risk |

---

## 🥈 Silver: reviewer validation

`validation/reviewer.py` makes a second Gemini call that receives the retrieved sources (and,
for "both" queries, the data answer) and checks each claim. It reviews the answer the user relies
on: the qualitative answer, or the synthesis for "both" queries. The verdict prints **before**
the answer.

**Developed against known cases** (`test_reviewer.py`): a correct answer, a wrong fact with a
citation, the two-error synthesis (#5), a "3.77 matches 3.7" error, and a correct comparison
(false-alarm check).

| Round | Change (one variable at a time) | Score |
|---|---|---|
| 1 | Baseline: ask directly for `supported: true/false` | 2/5 — flagged our own data as a "claim"; false alarm on a correct comparison |
| 2 | Label sources: `DOCUMENT SOURCES` / `DATA SOURCE`, "treat the CONTEXT as true" | 4/5 — one pass was luck (it flipped on the next run) |
| 3 | `thinking_level="low"` | No effect — **0 thinking tokens**; only visible because thinking was instrumented |
| 4 | **Show your work**: per-claim `{claim, evidence, correct}` written *before* each verdict; overall verdict computed in code | **5/5**, every flag for the right reason |

Round 4 output:
```
[PASS] 2. Wrong fact WITH citation
  - Passwords must be at least 8 characters long  (evidence: Passwords must be at least 14 characters long)
[PASS] 3. Synthesis v2: 4.0 and 3.7 comparison errors
  - ...above Spoonful's target of 4.0 in most departments  (evidence: ... Customer Care at 3.69, Finance at 3.64 ...)
  - ...above the ... benchmark of 3.7  (evidence: ... Customer Care is 3.69 which is not > 3.7)
[PASS] 4. '3.77 matches 3.7'
[PASS] 5. Correct comparison (false-alarm check)
```

Live in the CLI it returned correct verdicts on both a qualitative and a "both" query (true
negatives, verified by hand).

**Design choices:** structured JSON output (no parsing of free text); **fail closed** (an
unreadable review counts as flagged); the verdict is computed in code from the individual checks.

**Lessons:** both real improvements came from framing the task (labelled input, structured
output), not from model settings; and visible reasoning is auditable where hidden "thinking" is not.

**Limitations:** single test run per round, and the reviewer showed run-to-run variance;
it checks truth, not relevance (it accepted comparing the company-wide 3.77 to the warehouse-only
3.4 benchmark — true but irrelevant); it trusts the data source, so it cannot catch a wrong SQL
result like the JOIN in Trust-but-Verify #4.

---

## 🥇 Tokenomics

Pricing (`gemini-3.5-flash-lite`, paid tier): **$0.30 / 1M input**, **$2.50 / 1M output**
(output includes thinking). Logged costs show what the free-tier testing would cost when paid.
Reproduce the analysis with `python analyze_tokenomics.py`.

### What the log shows

57 model calls · 20 query runs · 11 distinct queries · 60,024 input / 11,169 output tokens ·
**$0.0459 total**.

| Agent | Calls | Avg in | Avg out | Avg cost / call | Share of spend |
|---|---|---|---|---|---|
| qualitative | 15 | 2,757 | 437 | $0.00192 | **63%** |
| quantitative | 14 | 421 | 196 | $0.00062 | 19% |
| manager-synthesis | 6 | 805 | 236 | $0.00083 | 11% |
| reviewer | 2 | 3,072 | 213 | $0.00145 | 6% |
| manager-classifier | 20 | 90 | 1 | $0.00003 | 1% |

| Query type | Typical cost per query | Per 1,000 queries |
|---|---|---|
| quantitative | $0.0002 – $0.0010 | $0.22 – $0.99 |
| qualitative (with review) | ~$0.0019 | ~$1.92 |
| both (with synthesis + review) | ~$0.0049 | ~$4.86 |

1. **Output tokens are 16% of tokens but 61% of cost** (output is 8.3× the price of input).
   Verbose answers, not large contexts, drive spend.
2. **The qualitative agent is 63% of spend.** Every call sends 5 chunks (~2,750 tokens) and broad
   questions get long answers (437 tokens on average; 612 for "How do we handle customer
   complaints?" vs 30 for "What is the refund approval limit...?" — same context, 60% cheaper).
3. **Routing is nearly free:** the classifier is 1% of spend and decides which expensive calls to make.
4. **Verification costs as much as generation:** the reviewer re-reads all the sources, so its
   cost scales with context size, not answer length. On "How long must passwords be?" the review
   ($0.00102) cost more than the answer ($0.00087).
5. **Same question, different cost:** the sales "both" query cost $0.0044 then $0.0033 —
   the document answer was 664 then 278 output tokens.

Note: the brief's `cost_per_1000_queries` field multiplies a single *call* by 1,000. A query
is 3–6 calls, so per-query figures above are computed by grouping calls into runs.

### Concrete optimisation: constrain the quantitative interpretation

**Change** (`agents/quantitative.py`, interpretation prompt), driven by the failures in
Trust-but-Verify #2 and #3:

```
Describe only what these results show. Do not speculate about causes or recommend policies.
If the question asks for information not in these results, say so in one sentence.
Keep it under 150 words.
```

**Measured on the same query** (employee satisfaction, quantitative agent, from the log):

| | Output tokens | Cost per call |
|---|---|---|
| Before | 591 | $0.001666 |
| After (7 runs) | 106 avg (58–215) | $0.000370 avg |
| **Change** | **−82%** | **−78%** |

**Quality did not degrade — it improved:** the before-answer contained a fake benchmark,
invented company policies and was cut off mid-sentence; every after-answer states the figures
and says in one sentence what the data does not cover.

### Further opportunities (not implemented)

- **Qualitative answer length** (the largest cost): the same "describe only what's asked,
  be concise" constraint would cut the 437-token average.
- **`top_k` 5 → 3** would cut ~40% of qualitative and reviewer input; in retrieval testing the
  chunk holding the answer ranked 1st or 2nd for the queries checked, but this needs re-testing before adopting.
- **Make the reviewer optional** for low-stakes questions — it adds 39–53% to a query's cost.

### Logging caveat

`candidates_token_count` excludes thinking tokens (billed as output). With
`thinking_level="minimal"` no thinking was recorded, so the log is accurate; `reviewer.py` adds
`thoughts_token_count` explicitly in case thinking ever occurs.

---

## Design decisions and departures from the brief

All changes were made in response to an observed failure (documented above), not in advance.

1. **Claude → Gemini** translation; `thinking_level="minimal"` on agent calls.
2. **Qualitative:** grounding rules moved into `system_instruction` (the checkpoint calls the
   system prompt non-negotiable); context-only, exact refusal sentence and citation rules kept.
3. **Quantitative:** fences stripped before `validate_sql`; schema context names SQLite, the
   date format and that tables are not linked; SQL and interpretation prompts constrained (Fix 1);
   Gemini service errors re-raised instead of reported as SQL failures.
4. **Manager:** synthesis step for "both" queries (validated and logged); reviewer integration.
5. **All clients:** SDK retries for 5xx errors (the SDK makes one attempt by default; 429 excluded).
6. **`main.py`:** catches Gemini service errors and keeps the session alive.
7. **Logger:** Gemini prices.

**Unchanged by design:** `validate_sql`, `validator.py`, `ingest.py`, chunk size 500.
`validate_sql`'s known false positives (CTEs, columns containing "UPDATE") were tested and
documented but never occurred with real model output.

## Known limitations

- NL→SQL is non-deterministic: the same question produced an overall average on some runs and
  a per-department breakdown on others (only the latter surfaces the Operations finding).
- The 256-token embedding window truncates 500-word chunks; fine at 7 chunks, a risk at scale.
- `classify()` would misroute a reply like `"Quantitative."` and crash on an empty reply; neither
  occurred in live testing (every reply was a clean single word).
- Validation catches unsupported claims, not wrong data from a valid-but-wrong SQL query.

## Testing

Each component was tested on its own before integration. Scripts are run from the project root;
those marked *free* make no model calls.

| Script | Covers |
|---|---|
| `smoke_test.py` | Gemini connectivity |
| `test_retrieval.py` *(free)* | ChromaDB relevance and distances |
| `test_qualitative.py` | retrieval/prompt structure (free) + grounding, refusal, injection |
| `test_quantitative.py` | `validate_sql` (free, 9 cases) + live NL→SQL (`--live`) |
| `test_validator.py` | validator on real outputs (free) + both brief checkpoints (`--live`) |
| `test_logger.py` *(free)* | cost arithmetic, in a temp folder so the real log stays clean |
| `test_manager.py` | classifier parsing edge cases (free) + live routing (`--live`) |
| `test_reviewer.py` | reviewer against 5 known-correct / known-wrong answers |
