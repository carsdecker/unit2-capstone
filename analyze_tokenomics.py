# analyze_tokenomics.py — summarises tokenomics_log.jsonl for the README (no model calls).
#   python analyze_tokenomics.py
import json
from collections import defaultdict

with open("tokenomics_log.jsonl") as f:
    entries = [json.loads(line) for line in f if line.strip()]

# Each log line is ONE model call. A query is several calls, and every query run starts
# with exactly one manager-classifier call, so group calls into runs at each classifier.
runs = []
for e in entries:
    if e["agent"] == "manager-classifier":
        runs.append({"query": e["query"], "calls": []})
    runs[-1]["calls"].append(e)

total_cost = sum(e["cost_usd"] for e in entries)
total_in = sum(e["input_tokens"] for e in entries)
total_out = sum(e["output_tokens"] for e in entries)
print(f"Calls logged: {len(entries)} | Query runs: {len(runs)} | "
      f"Distinct queries: {len({r['query'] for r in runs})}")
print(f"Tokens: {total_in:,} in / {total_out:,} out | Total cost: ${total_cost:.4f}")
print(f"Share of cost from output tokens: "
      f"{sum(e['output_tokens'] / 1000 * 0.0025 for e in entries) / total_cost:.0%}\n")

print("BY AGENT (per call)")
by_agent = defaultdict(list)
for e in entries:
    by_agent[e["agent"]].append(e)
print(f"  {'agent':20} {'calls':>5} {'avg in':>7} {'avg out':>8} {'avg cost':>10} {'share':>6}")
for agent, es in sorted(by_agent.items(), key=lambda kv: -sum(e["cost_usd"] for e in kv[1])):
    cost = sum(e["cost_usd"] for e in es)
    print(f"  {agent:20} {len(es):5} {sum(e['input_tokens'] for e in es) / len(es):7.0f} "
          f"{sum(e['output_tokens'] for e in es) / len(es):8.0f} {cost / len(es):10.6f} {cost / total_cost:6.0%}")

print("\nBY QUERY RUN (all runs; runs cut short by 503 errors during testing show fewer calls)")
for r in runs:
    agents = [c["agent"] for c in r["calls"]]
    route = ("both" if "manager-synthesis" in agents or ("qualitative" in agents and "quantitative" in agents)
             else "qualitative" if "qualitative" in agents else "quantitative" if "quantitative" in agents
             else "incomplete")
    cost = sum(c["cost_usd"] for c in r["calls"])
    print(f"  ${cost:.6f}  {route:12} {len(agents)} calls  {r['query'][:70]}")
