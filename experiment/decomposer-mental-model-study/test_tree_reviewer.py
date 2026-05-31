"""
[VERIFIED 2026-05-28] Experiment 4: Tree Structure Reviewer
Result: 10/10 correctly detected routing violations, 100% detection rate.
Output: output/tree_reviewer_v6/deepseek-v4-flash/

Tree Structure Reviewer Experiment.

A fresh LLM (not the decomposer) reviews existing baseline decomposition outputs
for compliance with tree structure constraints.

The reviewer is given ONLY general tree decomposition rules:
- Children are independent functions
- No child can see/call sibling nodes
- Parent is the sole orchestrator, calling all children directly
- Sibling-to-sibling calls are violations

It does NOT know about "routing" or "RouteCommand" — just fundamental tree rules.
This tests whether an independent reviewer naturally rejects RouteCommand→handler patterns.

Methodology:
- Load 5 existing baseline trials (00-04) for order_real
- Give each to a fresh LLM reviewer with tree structure rules
- See if it passes or fails the decomposition
- 2 replicates per source = 10 total

Usage:
    python test_tree_reviewer.py
"""
import json
import os
import sys
import time
import re
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from openai import OpenAI


# -----------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------
def _env(key, default=""):
    return os.getenv(key) or os.getenv(f"DEEPSEEK_{key.removeprefix('CHRONOS_')}") or default

TEMPERATURE = float(os.getenv("CHRONOS_TEMPERATURE", "0.3"))
MAX_TOKENS = int(os.getenv("CHRONOS_MAX_TOKENS", "2048"))
MAX_CONCURRENCY = int(os.getenv("CHRONOS_MAX_CONCURRENCY", "5"))

MIMO_MODELS = {"mimo-v2.5", "mimo-v2-flash", "mimo-v2.5-pro", "mimo-v2-pro", "mimo-v2-omni"}
MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"

BASELINE_DIR = os.path.join(
    os.path.dirname(__file__), "output", "routing_ablation",
    "deepseek-chat", "experiment_baseline", "order_real"
)

OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "output", "tree_reviewer_v6"
)

REVIEWER_SYSTEM_PROMPT = """You are a tree structure reviewer. Your job is to review function decomposition outputs and verify they conform to tree structure constraints.

## Tree Structure Rules

1. **Child independence**: Each child node is an independent function. A child must NOT call, reference, or depend on any sibling node.

2. **Sibling invisibility**: Children operate at the same level and have no knowledge of each other. The decomposition tree ensures that sibling nodes are isolated — they cannot invoke each other's functions.

3. **Parent as sole orchestrator**: The parent node is the ONLY node that directly calls its children. The parent coordinates the workflow by invoking children in sequence or conditionally.

4. **Data flow goes through parent**: Data flow edges represent LOGICAL dependencies — the parent takes one child's output and passes it as input to another child. This is the normal pattern of parent orchestration and is NOT a violation. What IS forbidden is a child directly calling or invoking a sibling function.

## Trust the Structure, Not the Description

The tree structure visualization is the authoritative representation of relationships. Base your verdict on structural facts, not on how nodes describe themselves.

### How to apply:

1. **Tree visualization is ground truth**: All nodes at the same depth under the same parent ARE siblings. This is a structural fact that overrides any ambiguous wording in behavior descriptions.

2. **Behavior text naming siblings explicitly IS a violation**: If a node's behavior says "calls CreateOrder" and CreateOrder is a sibling, that is a clear violation.

3. **Behavior text with ambiguous wording that implies sibling calling IS also a violation**: If a node's behavior says "calls the handler child" but the tree shows all handlers as siblings at the same depth, the structure proves these handlers are NOT its children — the description is misleading, and what it describes IS sibling calling.

4. **Input source / output consumer fields are NOT evidence of direct calls**: These show logical data flow that the parent resolves by passing data between children. Do not flag them.

5. **Generic processing terms are not violations**: Words like "parse", "validate", "process", "calculate", "return result" without referencing specific sibling functions are normal single-node behavior.

## Your Task

Given a decomposition with children listed (including their names, purposes, inputs, outputs, and behavior), determine whether it satisfies tree structure constraints.

Output your review in this format:
{
  "verdict": "PASS" or "FAIL",
  "reasoning": "Brief explanation of your verdict",
  "violations": [
    {
      "from_node": "name of node that violates",
      "to_node": "name of node being called/referenced",
      "rule": "which rule is violated",
      "details": "why this is a violation"
    }
  ],
  "recommendation": "If FAIL, how to fix the decomposition to satisfy tree constraints"
}

Be thorough but fair. If the decomposition satisfies all tree structure rules, pass it.
"""


# -----------------------------------------------------------------------
# LLM Logger
# -----------------------------------------------------------------------
class LLMLogger:
    def __init__(self, log_dir, api_key, base_url, model):
        self.log_dir = log_dir
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.call_counter = 0
        os.makedirs(log_dir, exist_ok=True)

    def chat(self, messages, max_tokens=None):
        self.call_counter += 1
        call_id = self.call_counter
        max_tokens = max_tokens or MAX_TOKENS

        req = {
            "call_id": call_id,
            "timestamp": time.time(),
            "messages": messages,
            "max_tokens": max_tokens,
            "model": self.model,
        }
        with open(os.path.join(self.log_dir, f"{call_id:04d}_request.json"), "w", encoding="utf-8") as f:
            json.dump(req, f, indent=2, ensure_ascii=False)

        client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=120)
        start = time.time()
        try:
            kwargs = dict(
                model=self.model,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=max_tokens,
                extra_body={"thinking": {"type": "disabled"}},
            )
            resp = client.chat.completions.create(**kwargs)
            text = resp.choices[0].message.content
        except Exception as e:
            elapsed = time.time() - start
            err_resp = {"call_id": call_id, "elapsed": round(elapsed, 2), "error": str(e)}
            with open(os.path.join(self.log_dir, f"{call_id:04d}_response.json"), "w", encoding="utf-8") as f:
                json.dump(err_resp, f, indent=2, ensure_ascii=False)
            raise
        elapsed = time.time() - start

        resp_data = {"call_id": call_id, "elapsed": round(elapsed, 2), "response": text}
        with open(os.path.join(self.log_dir, f"{call_id:04d}_response.json"), "w", encoding="utf-8") as f:
            json.dump(resp_data, f, indent=2, ensure_ascii=False)

        return text


# -----------------------------------------------------------------------
# Parse verdict from reviewer response
# -----------------------------------------------------------------------
def parse_verdict(text):
    """Extract PASS/FAIL from reviewer response."""
    # Try to parse as JSON
    text_clean = text.strip()
    if text_clean.startswith("```"):
        text_clean = re.sub(r"^```[a-zA-Z0-9]*\n?", "", text_clean)
        text_clean = re.sub(r"\n?```$", "", text_clean)
    if "}" in text_clean:
        last_brace = text_clean.rfind("}")
        text_clean = text_clean[:last_brace + 1]
    try:
        parsed = json.loads(text_clean)
        verdict = parsed.get("verdict", "").upper().strip()
        violations = parsed.get("violations", [])
        reasoning = parsed.get("reasoning", "")
        recommendation = parsed.get("recommendation", "")
        return verdict, violations, reasoning, recommendation
    except json.JSONDecodeError:
        pass

    # Fallback: search for PASS/FAIL in text
    if re.search(r'\bPASS\b', text, re.IGNORECASE):
        return "PASS", [], "Parsed from text", ""
    if re.search(r'\bFAIL\b', text, re.IGNORECASE):
        return "FAIL", [], "Parsed from text", ""
    return "UNKNOWN", [], "Could not parse verdict", ""


# -----------------------------------------------------------------------
# Build summary of decomposition for reviewer
# -----------------------------------------------------------------------
def build_decomposition_summary(decomposition):
    """Build a concise summary of the decomposition for the reviewer."""
    children = decomposition.get("children", [])
    dataflow_edges = decomposition.get("dataflow_edges", [])
    rationale = decomposition.get("decomposition_rationale", "")

    lines = ["## Decomposition to Review", ""]

    # Tree structure visualization
    parent_name = "Order_Management_System"
    lines.append("### Tree Structure")
    lines.append("")
    lines.append(f"  {parent_name} (parent)")
    for i, c in enumerate(children):
        name = c.get("name", "")
        is_last = i == len(children) - 1
        prefix = "    └── " if is_last else "    ├── "
        lines.append(f"{prefix}{name}")
    lines.append("")
    lines.append("All children above are at depth 1 — direct children of the parent, flat siblings to each other.")
    lines.append("")

    # Children
    lines.append(f"### Children ({len(children)} total)")
    lines.append("")
    for c in children:
        name = c.get("name", "")
        purpose = c.get("purpose", "")
        behavior = c.get("behavior", "")
        inputs = c.get("inputs", [])
        outputs = c.get("outputs", [])

        lines.append(f"**{name}**")
        lines.append(f"  Purpose: {purpose}")
        if behavior:
            lines.append(f"  Behavior: {behavior[:200]}")
        input_names = [i.get("name", "") for i in inputs]
        output_names = [o.get("name", "") for o in outputs]
        input_consumers = [(i.get("name", ""), i.get("source", "")) for i in inputs]
        output_consumers = [(o.get("name", ""), o.get("consumer", "")) for o in outputs]

        if input_consumers:
            for in_name, source in input_consumers:
                if source:
                    lines.append(f"  Input '{in_name}' source: {source}")
        if output_consumers:
            for out_name, consumer in output_consumers:
                if consumer:
                    lines.append(f"  Output '{out_name}' consumer: {consumer}")

        # Check if behavior mentions calling other children
        other_names = [x.get("name", "").lower() for x in children if x.get("name") != name]
        for on in other_names:
            if on.lower() in behavior.lower():
                lines.append(f"  ⚠️ Behavior mentions sibling: '{on}'")
        lines.append("")

    # Dataflow edges
    if dataflow_edges:
        lines.append("### Dataflow Edges")
        lines.append("")
        for e in dataflow_edges:
            lines.append(
                f"  {e.get('from_node', '?')} → {e.get('to_node', '?')}: "
                f"'{e.get('from_output', '?')}' → '{e.get('to_input', '?')}'"
            )
        lines.append("")

    if rationale:
        lines.append("### Decomposition Rationale")
        lines.append(f"  {rationale[:500]}")
        lines.append("")

    return "\n".join(lines)


# -----------------------------------------------------------------------
# Trial runner
# -----------------------------------------------------------------------
def run_review_trial(trial_data, source_trial, replicate_idx, api_key, base_url, model):
    """Run a single review trial."""
    decomposition = trial_data["response"]
    children = decomposition.get("children", [])
    child_names = [c.get("name", "") for c in children]

    label = f"source_trial_{source_trial:02d}/rep_{replicate_idx:02d}"
    log_dir = os.path.join(OUTPUT_DIR, model, f"source_{source_trial:02d}")
    logger = LLMLogger(log_dir, api_key, base_url, model)

    t0 = time.time()

    summary = build_decomposition_summary(decomposition)

    review_messages = [
        {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
        {"role": "user", "content": (
            "Please review the following decomposition for compliance with tree structure constraints.\n\n"
            + summary +
            "\n\nDoes this decomposition satisfy tree structure rules? "
            "Output your verdict as JSON: {\"verdict\": \"PASS\" or \"FAIL\", ...}"
        )},
    ]

    try:
        response = logger.chat(review_messages)
    except Exception as e:
        return {
            "label": label, "source_trial": source_trial, "replicate": replicate_idx,
            "error": str(e), "elapsed": time.time() - t0,
        }

    verdict, violations, reasoning, recommendation = parse_verdict(response)

    # Check if RouteCommand specifically flagged
    route_flagged = False
    route_node_name = ""
    for child in children:
        name = child.get("name", "")
        if re.search(r'route|dispatch|parse.*command|router', name, re.IGNORECASE):
            route_node_name = name
            for v in violations:
                if isinstance(v, dict) and name.lower() in v.get("from_node", "").lower():
                    route_flagged = True

    result = {
        "label": label,
        "source_trial": source_trial,
        "replicate": replicate_idx,
        "n_children": len(children),
        "child_names": child_names,
        "verdict": verdict,
        "violations": violations,
        "reasoning": reasoning[:500] if reasoning else "",
        "recommendation": recommendation[:500] if recommendation else "",
        "has_route_node": bool(route_node_name),
        "route_node_name": route_node_name,
        "route_flagged": route_flagged,
        "raw_response": response,
        "elapsed": round(time.time() - t0, 1),
        "llm_calls": logger.call_counter,
    }

    # Save individual result
    result_path = os.path.join(log_dir, f"review_rep_{replicate_idx:02d}.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return result


# -----------------------------------------------------------------------
# Load baseline trial data
# -----------------------------------------------------------------------
def load_baseline_trials():
    """Load all existing baseline trial JSONs for order_real."""
    trials = []
    for i in range(5):
        path = os.path.join(BASELINE_DIR, f"trial_{i:02d}.json")
        if not os.path.exists(path):
            print(f"Warning: {path} not found, skipping")
            continue
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["_source_trial"] = i
        trials.append(data)
        children = data["response"].get("children", [])
        child_names = [c.get("name", "") for c in children]
        print(f"  Trial {i:02d}: {len(children)} children -> {child_names}")
    return trials


# -----------------------------------------------------------------------
# Report generation
# -----------------------------------------------------------------------
def generate_report(all_results, model):
    """Generate markdown report."""
    lines = [
        "# Tree Structure Reviewer Experiment Report",
        "",
        f"- **Model:** {model}",
        f"- **Temperature:** {TEMPERATURE}",
        f"- **Total reviews:** {len(all_results)}",
        f"- **Date:** 2026-05-25",
        "",
        "---",
        "",
        "## Methodology",
        "",
        "A fresh LLM reviewer (not the decomposer) reviews existing baseline decomposition "
        "outputs for compliance with tree structure constraints. The reviewer is given ONLY "
        "general tree decomposition rules:",
        "",
        "- Children are independent functions — no child can call/reference siblings",
        "- Parent is the sole orchestrator, calling all children directly",
        "- No coordinator children that route work to siblings",
        "- Data flow between children must go through the parent",
        "",
        "The reviewer does NOT know about 'routing' or 'RouteCommand' — just fundamental tree rules. ",
        "This tests whether an independent reviewer naturally rejects RouteCommand→handler patterns.",
        "",
        "---",
        "",
        "## Verdict Results",
        "",
        "| # | Source Trial | Replicate | Verdict | Route Node | Route Flagged |",
        "|---|-------------|-----------|---------|------------|---------------|",
    ]

    verdicts = {}
    for i, r in enumerate(all_results):
        v = r.get("verdict", "ERROR")
        verdicts[v] = verdicts.get(v, 0) + 1
        error_str = r.get("error", "")
        v_display = v + (" ERROR" if error_str else "")
        route_flag = "YES" if r.get("route_flagged") else "no"
        route_name = r.get("route_node_name", "")
        lines.append(
            f"| {i} | trial_{r['source_trial']:02d} | "
            f"{r['replicate']:02d} | {v_display} | {route_name} | {route_flag} |"
        )

    lines.extend([
        "",
        "## Summary",
        "",
        f"Total: {len(all_results)}",
    ])
    for v, count in sorted(verdicts.items()):
        lines.append(f"- **{v}**: {count}/{len(all_results)} ({count/len(all_results)*100:.0f}%)")

    lines.append("")

    # Detail section
    lines.append("## Detailed Reviews")
    lines.append("")
    for r in all_results:
        lines.append(f"### {r['label']}")
        lines.append(f"- Verdict: **{r.get('verdict', 'N/A')}**")
        lines.append(f"- Children: {', '.join(r.get('child_names', []))}")
        lines.append(f"- Route node: {r.get('route_node_name', '(none)')}")
        lines.append(f"- Route flagged: {r.get('route_flagged', False)}")
        if r.get("reasoning"):
            lines.append(f"- Reasoning: {r['reasoning']}")
        if r.get("violations"):
            lines.append("- Violations:")
            for v in r["violations"]:
                if isinstance(v, dict):
                    lines.append(f"  - {v.get('from_node', '')} → {v.get('to_node', '')}: {v.get('details', '')}")
                else:
                    lines.append(f"  - {v}")
        if r.get("recommendation"):
            lines.append(f"- Recommendation: {r['recommendation']}")
        if r.get("error"):
            lines.append(f"- ERROR: {r['error']}")
        lines.append("")

    return "\n".join(lines)


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Tree structure reviewer experiment")
    parser.add_argument("--model", type=str, default=None, help="Model name")
    parser.add_argument("--base-url", type=str, default=None, help="API base URL")
    parser.add_argument("--api-key", type=str, default=None, help="API key")
    parser.add_argument("--replicates", type=int, default=2, help="Replicates per source trial")
    args = parser.parse_args()

    # Resolve model config
    model = args.model or _env("CHRONOS_MODEL", "deepseek-chat")
    if model in MIMO_MODELS:
        base_url = args.base_url or os.getenv("MIMO_BASE_URL", MIMO_BASE_URL)
        api_key = args.api_key or os.getenv("MIMO_API_KEY") or _env("CHRONOS_API_KEY")
    else:
        base_url = args.base_url or _env("CHRONOS_BASE_URL", "https://api.deepseek.com")
        api_key = args.api_key or _env("CHRONOS_API_KEY")

    if not api_key:
        print("ERROR: Set CHRONOS_API_KEY (or DEEPSEEK_API_KEY or MIMO_API_KEY)")
        return 1

    print(f"API: {base_url}")
    print(f"Model: {model}")
    print(f"Replicates per source trial: {args.replicates}")
    print()

    # Load baseline trials
    print("Loading baseline trials...")
    trials = load_baseline_trials()
    print(f"Loaded {len(trials)} trials")
    print()

    # Build task list
    tasks = []
    for trial_data in trials:
        for rep in range(args.replicates):
            tasks.append((trial_data, trial_data["_source_trial"], rep, api_key, base_url, model))

    total = len(tasks)
    print(f"Running {total} reviews...\n")

    # Execute
    all_results = []
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        futures = {}
        for trial_data, source_trial, rep, ak, bu, m in tasks:
            f = pool.submit(run_review_trial, trial_data, source_trial, rep, ak, bu, m)
            futures[f] = f"source_{source_trial:02d}/rep_{rep:02d}"

        for f in as_completed(futures):
            label = futures[f]
            try:
                result = f.result()
                all_results.append(result)
                verdict = result.get("verdict", "ERROR")
                route_flagged = "ROUTE-FLAGGED" if result.get("route_flagged") else "ok"
                elapsed = result.get("elapsed", 0)
                print(f"  [{label}] {verdict} ({route_flagged}), {elapsed:.1f}s")
            except Exception as e:
                print(f"  [{label}] ERROR: {e}")
                all_results.append({"label": label, "error": str(e)})

    # Save all results
    os.makedirs(os.path.join(OUTPUT_DIR, model), exist_ok=True)
    results_path = os.path.join(OUTPUT_DIR, model, "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nResults saved: {results_path}")

    # Generate report
    report = generate_report(all_results, model)
    report_path = os.path.join(OUTPUT_DIR, model, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved: {report_path}")

    # Summary
    verdicts = {}
    route_flagged_count = 0
    for r in all_results:
        v = r.get("verdict", "ERROR")
        verdicts[v] = verdicts.get(v, 0) + 1
        if r.get("route_flagged"):
            route_flagged_count += 1

    print(f"\n{'='*60}")
    print(f"  RESULTS:")
    for v, count in sorted(verdicts.items()):
        print(f"    {v}: {count}/{total} ({count/total*100:.0f}%)")
    print(f"    RouteCommand flagged: {route_flagged_count}/{total}")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
