"""
Rejudge Exp03 outputs using corrected criteria from guides/EXP01_EXP03_REJUDGE_GUIDE.md.

Key changes:
1. Routing judge uses Exp01 criteria (dataflow_sketch primary evidence)
2. Dangling input reclassified: parent_source/resource_source/constant are NOT hard dangling
3. Resource coverage considers global_vars + data_operations + requested_capabilities
4. cannot_compose renamed to llm_composition_review_failure
"""

import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
INPUT_DIR = SCRIPT_DIR / "output" / "multistage_exp03_pipeline_regression" / "deepseek-v4-flash"
OUTPUT_DIR = SCRIPT_DIR / "output" / "multistage_exp03_pipeline_regression_rejudged" / "deepseek-v4-flash"

CONDITIONS = ["single_stage_baseline", "single_stage_notraditional", "three_stage"]
CASES = ["OrderSystem", "ChatApp", "PatientPortal", "BuildSystem", "DataPipeline"]

# --- Reuse Exp01 routing judge patterns ---
ROUTER_NAME_PATTERNS = [
    r"^Route", r"Router$", r"^Dispatch", r"Dispatcher$",
    r"^Coordinator$", r"^CommandHandler$", r"^Controller$",
]
NOT_ROUTER_PATTERNS = [r"^Parse", r"^Validate", r"^ProcessCommand"]
CONTROL_CALL_VERBS = [
    r"\bcalls?\b", r"\binvoke[sd]?\b", r"\bdispatch(?:es|ed|ing)?\b",
    r"\broute[sd]?\b", r"\bdelegat(?:es|ed|ing)?\b", r"\bselects?\b.*\bchild\b",
    r"\bwhich child to call\b", r"\broute to handler\b", r"\bdispatch to\b",
    r"\bselect which\b", r"\brouting\b.*\bcommand\b",
]
PARENT_ORCHESTRATION_KEYWORDS = [
    r"\bparent orchestrates\b", r"\bparent selects\b", r"\bparent passes\b",
    r"\bparent decides\b", r"\bparent routes\b",
]

# --- Dangling input source classification (from guide 4.2) ---
VALID_PARENT_SOURCES = [
    r"^parent input", r"^parent$", r"^parent input\.", r"^parent\b",
    r"^known parent input",
]
VALID_RESOURCE_SOURCES = [
    r"^internal leaf access", r"^global variable", r"^data store",
    r"^known parent global var", r"^known parent data source",
    r"\bdata store\b", r"\bstore\b", r"\baccess\b",
]
VALID_CONSTANT_SOURCES = [
    r"^constant", r"^config", r"^default", r"^generated",
]
VALID_PREV_CHILD_SOURCES = [
    r"^previous child", r"output$", r"\boutput\b",
    r"^Child\w+", r"^[A-Z]\w+ output", r"^[A-Z]\w+\.",
]


def parse_json_response(filepath):
    """Parse a JSON response file."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "response" in data:
        raw = data["response"]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass
            return {"error": "parse_failed"}
    return data


def is_router_name(name):
    for pat in ROUTER_NAME_PATTERNS:
        if re.search(pat, name, re.IGNORECASE):
            for nrpat in NOT_ROUTER_PATTERNS:
                if re.search(nrpat, name, re.IGNORECASE):
                    return False
            return True
    return False


def has_control_call_text(text):
    if not text:
        return False
    for pat in CONTROL_CALL_VERBS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def has_parent_orchestration_text(text):
    if not text:
        return False
    for pat in PARENT_ORCHESTRATION_KEYWORDS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def normalize_node_name(name):
    name = name.strip()
    if name.lower() in ("parent", "parent input", "parent output"):
        return "parent"
    return name


def classify_source(source_str):
    """Classify a child input source into a category."""
    if not source_str:
        return "dangling_input"
    s = source_str.strip().lower()

    # parent_source
    for pat in VALID_PARENT_SOURCES:
        if re.search(pat, s, re.IGNORECASE):
            return "parent_source"

    # resource_source (data stores, internal leaf access)
    for pat in VALID_RESOURCE_SOURCES:
        if re.search(pat, s, re.IGNORECASE):
            return "resource_source"

    # constant_source
    for pat in VALID_CONSTANT_SOURCES:
        if re.search(pat, s, re.IGNORECASE):
            return "constant_source"

    # previous_child_output
    for pat in VALID_PREV_CHILD_SOURCES:
        if re.search(pat, source_str, re.IGNORECASE):
            return "previous_child_output_source"

    # Check for explicit "parent" in source
    if "parent" in s:
        return "parent_source"

    # Check for known parent input names
    if s.startswith("parent"):
        return "parent_source"

    return "ambiguous_source"


def judge_routing(children, dataflow, rationale):
    """Apply Exp01 routing judge. Returns (hard_routing, evidence_list)."""
    evidence = []
    child_names = {c.get("name", "") for c in children}
    child_map = {c.get("name", ""): c for c in children}

    # Classify edges
    sibling_edges = []
    for edge in dataflow:
        src = normalize_node_name(edge.get("from", edge.get("from_node", "")))
        dst = normalize_node_name(edge.get("to", edge.get("to_node", "")))
        if src == "parent" or dst == "parent":
            continue
        if src in child_names and dst in child_names:
            sibling_edges.append((src, dst, edge))

    # Check router nodes
    router_nodes = []
    for c in children:
        name = c.get("name", "")
        purpose = c.get("purpose", "")
        behavior = c.get("behavior", "")
        combined = f"{purpose} {behavior}"
        if is_router_name(name) and has_control_call_text(combined):
            router_nodes.append(name)
            evidence.append({
                "category": "router_node",
                "field": "child.purpose+behavior",
                "child": name,
                "target": "",
                "snippet": combined[:200],
                "reason": f"Router-like name with control-call semantics"
            })

    # Check sibling edges
    hard_calls = []
    ambiguous_calls = []
    for src, dst, edge in sibling_edges:
        src_child = child_map.get(src, {})
        src_text = f"{src_child.get('purpose', '')} {src_child.get('behavior', '')}"
        note = edge.get("note", "")
        if has_control_call_text(src_text) or has_control_call_text(note):
            hard_calls.append((src, dst))
            evidence.append({
                "category": "hard_routing",
                "field": "dataflow_sketch",
                "child": src,
                "target": dst,
                "snippet": f"{src} -> {dst}: {note}",
                "reason": "Sibling edge with control-call semantics"
            })
        else:
            ambiguous_calls.append((src, dst))
            evidence.append({
                "category": "ambiguous_direct_dataflow",
                "field": "dataflow_sketch",
                "child": src,
                "target": dst,
                "snippet": f"{src} -> {dst}: {note}",
                "reason": "Sibling edge without explicit control-call wording"
            })

    # Check parent-mediated
    parent_mediated = False
    for c in children:
        for so in c.get("semantic_outputs", []):
            if so.get("consumer", "") == "parent":
                parent_mediated = True
    if has_parent_orchestration_text(rationale):
        parent_mediated = True

    hard_routing = len(router_nodes) > 0 or len(hard_calls) > 0

    return {
        "hard_routing": hard_routing,
        "sibling_invocation": len(hard_calls) > 0,
        "router_node": len(router_nodes) > 0,
        "parent_mediated_dataflow": parent_mediated,
        "ambiguous_direct_dataflow": len(ambiguous_calls) > 0,
        "router_nodes": router_nodes,
        "hard_routing_calls": [{"from": s, "to": d} for s, d in hard_calls],
        "ambiguous_calls": [{"from": s, "to": d} for s, d in ambiguous_calls],
    }, evidence


def judge_dangling(children, parent_node=None):
    """Reclassify dangling inputs with proper source classification."""
    results = []
    for c in children:
        name = c.get("name", "")
        inputs = c.get("inputs", c.get("semantic_inputs", []))
        for inp in inputs:
            source = inp.get("source", "")
            source_class = classify_source(source)
            inp_name = inp.get("name", "")
            results.append({
                "child": name,
                "input": inp_name,
                "source": source,
                "source_class": source_class,
                "is_hard_dangling": source_class == "dangling_input",
            })
    hard_dangling = [r for r in results if r["is_hard_dangling"]]
    ambiguous = [r for r in results if r["source_class"] == "ambiguous_source"]
    return {
        "total_inputs": len(results),
        "hard_dangling_count": len(hard_dangling),
        "ambiguous_source_count": len(ambiguous),
        "hard_dangling": hard_dangling,
        "ambiguous_sources": ambiguous,
        "all_classifications": results,
    }


def normalize_op(op):
    """Normalize operation type."""
    op = op.lower().strip()
    if op in ("read_write", "read+write"):
        return "read_write"
    if op in ("read", "query", "get", "list"):
        return "read"
    if op in ("write", "update", "mutate", "create", "insert", "delete"):
        return "write"
    return op


def judge_resource_coverage(children, parent_gvs=None):
    """Check resource coverage across global_vars, data_operations, requested_capabilities."""
    child_resources = {}  # child_name -> set of (variable, normalized_op)
    all_child_vars = {}  # variable -> set of ops

    for c in children:
        name = c.get("name", "")
        child_resources[name] = set()

        # global_vars
        for gv in c.get("global_vars", []):
            var = gv.get("variable", gv.get("var", ""))
            op = normalize_op(gv.get("op", gv.get("operation_type", "read")))
            child_resources[name].add((var, op))
            all_child_vars.setdefault(var, set()).add(op)

        # data_operations
        for do in c.get("data_operations", []):
            src = do.get("source_name", "")
            op = normalize_op(do.get("operation_type", "read"))
            if src:
                child_resources[name].add((src, op))
                all_child_vars.setdefault(src, set()).add(op)

    # Check subset violation: each child's global_vars must be subset of parent's
    parent_vars = {}
    if parent_gvs:
        for gv in parent_gvs:
            var = gv.get("variable", gv.get("var", ""))
            op = normalize_op(gv.get("op", gv.get("operation_type", "read")))
            parent_vars.setdefault(var, set()).add(op)

    subset_violations = []
    if parent_vars:
        for c in children:
            name = c.get("name", "")
            for gv in c.get("global_vars", []):
                var = gv.get("variable", gv.get("var", ""))
                op = normalize_op(gv.get("op", "read"))
                if var not in parent_vars:
                    subset_violations.append({
                        "child": name, "variable": var, "op": op,
                        "reason": f"Variable '{var}' not in parent global_vars"
                    })

    # Check coverage gap
    coverage_gaps = []
    if parent_vars:
        for var, required_ops in parent_vars.items():
            child_ops = all_child_vars.get(var, set())
            for req_op in required_ops:
                covered = False
                if req_op == "read_write":
                    covered = "read_write" in child_ops or ("read" in child_ops and "write" in child_ops)
                elif req_op == "read":
                    covered = "read" in child_ops or "read_write" in child_ops
                elif req_op == "write":
                    covered = "write" in child_ops or "read_write" in child_ops
                if not covered:
                    coverage_gaps.append({
                        "variable": var, "required_op": req_op,
                        "child_ops": list(child_ops),
                        "reason": f"No child covers {var}:{req_op}"
                    })

    return {
        "subset_violations": subset_violations,
        "coverage_gaps": coverage_gaps,
        "child_resources": {k: list(v) for k, v in child_resources.items()},
    }


def judge_trial_from_stages(trial_dir, condition, case_name, trial_idx):
    """Judge a three-stage trial from stage files."""
    stage1_file = trial_dir / "stage1.json"
    result_file = trial_dir / "result.json"

    if not stage1_file.exists():
        return None

    stage1 = parse_json_response(stage1_file)
    old_result = {}
    if result_file.exists():
        with open(result_file, "r", encoding="utf-8") as f:
            old_result = json.load(f)

    children = stage1.get("children", [])
    dataflow = stage1.get("dataflow_sketch", stage1.get("dataflow_edges", []))
    rationale = stage1.get("decomposition_rationale", "")

    routing_result, routing_evidence = judge_routing(children, dataflow, rationale)
    dangling_result = judge_dangling(children)
    resource_result = judge_resource_coverage(children)

    return {
        "condition": condition,
        "case": case_name,
        "trial": trial_idx,
        "n_children": len(children),
        "child_names": [c.get("name", "") for c in children],
        "routing": routing_result,
        "dangling": {
            "hard_dangling_count": dangling_result["hard_dangling_count"],
            "ambiguous_source_count": dangling_result["ambiguous_source_count"],
            "hard_dangling": dangling_result["hard_dangling"],
            "ambiguous_sources": dangling_result["ambiguous_sources"],
        },
        "resource": {
            "subset_violations": resource_result["subset_violations"],
            "coverage_gaps": resource_result["coverage_gaps"],
        },
        "llm_composition_review_failure": old_result.get("cannot_compose", False),
        "old_cannot_compose": old_result.get("cannot_compose", False),
        "child_count_violation": len(children) > 10 or len(children) < 2,
        "parse_error": False,
        "evidence": routing_evidence,
    }


def judge_trial_from_response(trial_dir, condition, case_name, trial_idx):
    """Judge a single-stage trial from 0001_response.json."""
    response_file = trial_dir / "0001_response.json"
    result_file = trial_dir / "result.json"

    old_result = {}
    if result_file.exists():
        with open(result_file, "r", encoding="utf-8") as f:
            old_result = json.load(f)

    if not response_file.exists():
        # Fall back to old result only
        return {
            "condition": condition,
            "case": case_name,
            "trial": trial_idx,
            "n_children": old_result.get("n_children", 0),
            "child_names": old_result.get("child_names", []),
            "routing": {"hard_routing": old_result.get("has_routing", False)},
            "dangling": {"hard_dangling_count": len(old_result.get("dangling_inputs", [])),
                         "note": "reclassified from old data, raw unavailable"},
            "resource": {"note": "raw data unavailable"},
            "llm_composition_review_failure": old_result.get("cannot_compose", False),
            "old_cannot_compose": old_result.get("cannot_compose", False),
            "child_count_violation": old_result.get("child_count_violation", False),
            "parse_error": False,
            "evidence": [],
            "data_limitation": "raw child content unavailable for single-stage trial",
        }

    parsed = parse_json_response(response_file)
    if "error" in parsed and "children" not in parsed:
        return {
            "condition": condition,
            "case": case_name,
            "trial": trial_idx,
            "parse_error": True,
            "error": parsed.get("error"),
        }

    # For single-stage, the parsed output may have children directly or nested
    children = parsed.get("children", [])
    # dataflow_edges format uses from_node/to_node
    dataflow = parsed.get("dataflow_edges", parsed.get("dataflow_sketch", []))
    rationale = parsed.get("decomposition_rationale", "")

    routing_result, routing_evidence = judge_routing(children, dataflow, rationale)
    dangling_result = judge_dangling(children)
    resource_result = judge_resource_coverage(children)

    return {
        "condition": condition,
        "case": case_name,
        "trial": trial_idx,
        "n_children": len(children),
        "child_names": [c.get("name", "") for c in children],
        "routing": routing_result,
        "dangling": {
            "hard_dangling_count": dangling_result["hard_dangling_count"],
            "ambiguous_source_count": dangling_result["ambiguous_source_count"],
            "hard_dangling": dangling_result["hard_dangling"],
            "ambiguous_sources": dangling_result["ambiguous_sources"],
        },
        "resource": {
            "subset_violations": resource_result["subset_violations"],
            "coverage_gaps": resource_result["coverage_gaps"],
        },
        "llm_composition_review_failure": old_result.get("cannot_compose", False),
        "old_cannot_compose": old_result.get("cannot_compose", False),
        "child_count_violation": len(children) > 10 or len(children) < 2,
        "parse_error": False,
        "evidence": routing_evidence,
    }


def main():
    all_trials = []

    for condition in CONDITIONS:
        cond_dir = INPUT_DIR / condition
        if not cond_dir.exists():
            continue
        for case_name in CASES:
            case_dir = cond_dir / case_name
            if not case_dir.exists():
                continue
            for trial_dir in sorted(case_dir.iterdir()):
                if not trial_dir.is_dir() or not trial_dir.name.startswith("trial_"):
                    continue
                trial_idx = int(trial_dir.name.split("_")[1])

                if condition == "three_stage":
                    result = judge_trial_from_stages(trial_dir, condition, case_name, trial_idx)
                else:
                    result = judge_trial_from_response(trial_dir, condition, case_name, trial_idx)

                if result:
                    # Add old judge for comparison
                    old_file = trial_dir / "result.json"
                    if old_file.exists():
                        with open(old_file, "r", encoding="utf-8") as f:
                            old = json.load(f)
                        result["old_judge"] = {
                            "has_routing": old.get("has_routing"),
                            "dangling_inputs_count": len(old.get("dangling_inputs", [])),
                            "cannot_compose": old.get("cannot_compose"),
                            "global_var_union_gap_count": len(old.get("global_var_union_gap", [])),
                        }
                    all_trials.append(result)

    # Aggregate metrics by condition
    metrics_by_condition = {}
    for condition in CONDITIONS:
        ct = [t for t in all_trials if t["condition"] == condition and not t.get("parse_error")]
        n = len(ct)
        if n == 0:
            continue
        metrics_by_condition[condition] = {
            "trials": n,
            "hard_routing": sum(1 for t in ct if t.get("routing", {}).get("hard_routing")),
            "sibling_invocation": sum(1 for t in ct if t.get("routing", {}).get("sibling_invocation")),
            "ambiguous_direct_dataflow": sum(1 for t in ct if t.get("routing", {}).get("ambiguous_direct_dataflow")),
            "hard_dangling_input": sum(t.get("dangling", {}).get("hard_dangling_count", 0) for t in ct),
            "ambiguous_source": sum(t.get("dangling", {}).get("ambiguous_source_count", 0) for t in ct),
            "global_var_subset_violation": sum(len(t.get("resource", {}).get("subset_violations", [])) for t in ct),
            "resource_coverage_gap": sum(len(t.get("resource", {}).get("coverage_gaps", [])) for t in ct),
            "llm_composition_review_failure": sum(1 for t in ct if t.get("llm_composition_review_failure")),
            "child_count_violation": sum(1 for t in ct if t.get("child_count_violation")),
        }

    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {
        "model": "deepseek-v4-flash",
        "metrics_by_condition": metrics_by_condition,
        "trials": all_trials,
    }
    with open(OUTPUT_DIR / "results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    report = generate_report(results)
    with open(OUTPUT_DIR / "report.md", "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Rejudge complete. Output: {OUTPUT_DIR}")
    for cond, m in metrics_by_condition.items():
        print(f"  {cond}: hard_routing={m['hard_routing']}/{m['trials']}, "
              f"hard_dangling={m['hard_dangling_input']}, "
              f"llm_review_fail={m['llm_composition_review_failure']}/{m['trials']}")


def generate_report(results):
    metrics = results["metrics_by_condition"]
    trials = results["trials"]

    lines = [
        "# Exp03 Rejudge Report",
        "",
        "Model: `deepseek-v4-flash`",
        "",
        "## Key Changes from Old Judge",
        "",
        "1. `cannot_compose` renamed to `llm_composition_review_failure` (LLM reviewer, not real CodeGenerator)",
        "2. Dangling inputs reclassified: `parent input`, `internal leaf access`, `global variable` are NOT hard dangling",
        "3. Routing judge uses Exp01 criteria: `dataflow_sketch` is primary evidence, `behavior`/`purpose` confirm control calls",
        "4. Resource coverage considers `global_vars` + `data_operations` + `requested_capabilities`",
        "",
        "## Results Matrix (Condition x Metric)",
        "",
        "| Condition | Trials | hard_routing | sibling_inv | ambiguous_df | hard_dangling | ambiguous_src | gv_subset_viol | res_coverage_gap | llm_review_fail | child_count_viol |",
        "|-----------|--------|-------------|-------------|-------------|--------------|--------------|----------------|-----------------|----------------|-----------------|",
    ]

    for cond in CONDITIONS:
        m = metrics.get(cond)
        if not m:
            continue
        lines.append(
            f"| {cond} | {m['trials']} | {m['hard_routing']}/{m['trials']} | "
            f"{m['sibling_invocation']}/{m['trials']} | {m['ambiguous_direct_dataflow']}/{m['trials']} | "
            f"{m['hard_dangling_input']} | {m['ambiguous_source']} | "
            f"{m['global_var_subset_violation']} | {m['resource_coverage_gap']} | "
            f"{m['llm_composition_review_failure']}/{m['trials']} | {m['child_count_violation']}/{m['trials']} |"
        )

    lines.append("")

    # Old vs new comparison
    lines.append("## Old vs New Comparison")
    lines.append("")
    lines.append("| Condition | Old routing | New hard_routing | Old dangling | New hard_dangling | Old cannot_compose | New llm_review_fail |")
    lines.append("|-----------|------------|-----------------|-------------|-----------------|-------------------|-------------------|")

    for cond in CONDITIONS:
        ct = [t for t in trials if t["condition"] == cond and not t.get("parse_error")]
        n = len(ct)
        old_routing = sum(1 for t in ct if t.get("old_judge", {}).get("has_routing"))
        new_routing = sum(1 for t in ct if t.get("routing", {}).get("hard_routing"))
        old_dangling = sum(t.get("old_judge", {}).get("dangling_inputs_count", 0) for t in ct)
        new_dangling = sum(t.get("dangling", {}).get("hard_dangling_count", 0) for t in ct)
        old_compose = sum(1 for t in ct if t.get("old_judge", {}).get("cannot_compose"))
        new_review = sum(1 for t in ct if t.get("llm_composition_review_failure"))
        lines.append(f"| {cond} | {old_routing}/{n} | {new_routing}/{n} | {old_dangling} | {new_dangling} | {old_compose}/{n} | {new_review}/{n} |")

    lines.append("")

    # Verdict
    lines.append("## Verdict")
    lines.append("")

    three_stage_m = metrics.get("three_stage", {})
    notraditional_m = metrics.get("single_stage_notraditional", {})

    if three_stage_m and notraditional_m:
        ts_hr = three_stage_m.get("hard_routing", 0)
        nt_hr = notraditional_m.get("hard_routing", 0)
        ts_hd = three_stage_m.get("hard_dangling_input", 0)
        nt_hd = notraditional_m.get("hard_dangling_input", 0)

        if ts_hr <= nt_hr and ts_hd <= nt_hd:
            lines.append("- **PASS**: three_stage does not regress hard routing or hard deterministic failures vs notraditional.")
        elif ts_hr > nt_hr or ts_hd > nt_hd:
            lines.append("- **FAIL**: three_stage regresses on hard routing or hard deterministic failures.")
        else:
            lines.append("- **INCONCLUSIVE**: Ambiguity remains. Only llm_composition_review_failure data available, no real codegen.")

    lines.append("")
    lines.append("Note: Since no real CodeGenerator `cannot_compose` is measured, the verdict is limited to deterministic structural checks.")
    lines.append("")

    # Manual check section
    lines.append("## Manual Check Cases")
    lines.append("")
    manual = [
        ("three_stage", "OrderSystem", 0),
        ("three_stage", "DataPipeline", 0),
    ]
    for cond, case, ti in manual:
        t = next((x for x in trials if x["condition"] == cond and x["case"] == case and x["trial"] == ti), None)
        if not t:
            lines.append(f"### {cond}/{case}/trial_{ti:02d} — NOT FOUND")
            lines.append("")
            continue
        r = t.get("routing", {})
        lines.append(f"### {cond}/{case}/trial_{ti:02d}")
        lines.append("")
        lines.append(f"- **hard_routing**: {r.get('hard_routing')}")
        lines.append(f"- **parent_mediated**: {r.get('parent_mediated_dataflow')}")
        lines.append(f"- **ambiguous_direct_dataflow**: {r.get('ambiguous_direct_dataflow')}")
        lines.append(f"- **router_node**: {r.get('router_node')}")
        lines.append(f"- Children: {', '.join(t.get('child_names', []))}")
        if r.get("router_nodes"):
            lines.append(f"- Router nodes: {r['router_nodes']}")
        if r.get("hard_routing_calls"):
            lines.append(f"- Hard routing calls: {r['hard_routing_calls']}")
        if r.get("ambiguous_calls"):
            lines.append(f"- Ambiguous calls: {r['ambiguous_calls']}")
        lines.append(f"- Hard dangling: {t.get('dangling', {}).get('hard_dangling_count', 0)}")
        lines.append(f"- Ambiguous sources: {t.get('dangling', {}).get('ambiguous_source_count', 0)}")
        lines.append(f"- LLM review failure: {t.get('llm_composition_review_failure')}")
        for e in t.get("evidence", [])[:5]:
            lines.append(f"  - [{e['category']}] {e.get('child', '')} -> {e.get('target', '')}: {e['snippet'][:150]}")
        lines.append("")

    # Per-case breakdown for three_stage
    lines.append("## Per-Case Breakdown (three_stage)")
    lines.append("")
    lines.append("| Case | hard_routing | hard_dangling | ambiguous_src | llm_review_fail |")
    lines.append("|------|-------------|--------------|--------------|----------------|")
    for case in CASES:
        ct = [t for t in trials if t["condition"] == "three_stage" and t["case"] == case and not t.get("parse_error")]
        if not ct:
            continue
        hr = sum(1 for t in ct if t.get("routing", {}).get("hard_routing"))
        hd = sum(t.get("dangling", {}).get("hard_dangling_count", 0) for t in ct)
        am = sum(t.get("dangling", {}).get("ambiguous_source_count", 0) for t in ct)
        lr = sum(1 for t in ct if t.get("llm_composition_review_failure"))
        lines.append(f"| {case} | {hr}/{len(ct)} | {hd} | {am} | {lr}/{len(ct)} |")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
