"""
Exp03 Fixed-Input Stage3 Conservation Rejudge.

Reads from the fixed-input Stage3 conservation output directory.
Applies the same v2 judge logic (routing from Stage1, resource from merged_node,
parent globals from decomposer_cases). Adds stage3_interface_drift and
false_self_check detection.

Compares against the original v2 fixed-input baseline.
"""

import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
INPUT_DIR = SCRIPT_DIR / "output" / "multistage_exp03_fixed_stage3_conservation" / "deepseek-v4-flash"
OUTPUT_DIR = SCRIPT_DIR / "output" / "multistage_exp03_fixed_stage3_conservation_rejudged" / "deepseek-v4-flash"

# v2 results for comparison
V2_DIR = SCRIPT_DIR / "output" / "multistage_exp03_pipeline_regression_rejudged_v2" / "deepseek-v4-flash"

CASES = ["OrderSystem", "ChatApp", "PatientPortal", "BuildSystem", "DataPipeline"]

# --- Load parent cases ---
sys.path.insert(0, str(SCRIPT_DIR / "test_data"))
from decomposer_cases import ALL_CASES

CASE_BY_NAME = {}
for case in ALL_CASES:
    CASE_BY_NAME[case["node"].name] = case


# ========================================================================
# Routing judge (identical to conservation rejudge)
# ========================================================================

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
    r"\bcall (?:the )?(?:appropriate|correct|corresponding)\b",
    r"\binvoke the (?:appropriate|correct)\b",
]
PARENT_ORCHESTRATION_KEYWORDS = [
    r"\bparent orchestrates\b", r"\bparent selects\b", r"\bparent passes\b",
    r"\bparent decides\b", r"\bparent routes\b",
]


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


def parse_json_file(filepath):
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


def judge_routing(children, dataflow, rationale):
    evidence = []
    child_names = {c.get("name", "") for c in children}
    child_map = {c.get("name", ""): c for c in children}
    sibling_edges = []
    for edge in dataflow:
        src = normalize_node_name(edge.get("from", edge.get("from_node", "")))
        dst = normalize_node_name(edge.get("to", edge.get("to_node", "")))
        if src == "parent" or dst == "parent":
            continue
        if src in child_names and dst in child_names:
            sibling_edges.append((src, dst, edge))
    router_nodes = []
    for c in children:
        name = c.get("name", "")
        purpose = c.get("purpose", "")
        behavior = c.get("behavior", "")
        combined = f"{purpose} {behavior}"
        if is_router_name(name) and has_control_call_text(combined):
            router_nodes.append(name)
            evidence.append({"category": "router_node", "child": name, "reason": "Router-like name with control-call semantics"})
    hard_calls = []
    ambiguous_calls = []
    for src, dst, edge in sibling_edges:
        src_child = child_map.get(src, {})
        src_text = f"{src_child.get('purpose', '')} {src_child.get('behavior', '')}"
        note = edge.get("note", "")
        if has_control_call_text(src_text) or has_control_call_text(note):
            hard_calls.append((src, dst))
            evidence.append({"category": "hard_routing", "child": src, "target": dst, "reason": "Sibling edge with control-call semantics"})
        else:
            ambiguous_calls.append((src, dst))
    parent_mediated = False
    for c in children:
        for so in c.get("semantic_outputs", []):
            if so.get("consumer", "") == "parent":
                parent_mediated = True
    if has_parent_orchestration_text(rationale):
        parent_mediated = True
    return {
        "hard_routing": len(router_nodes) > 0 or len(hard_calls) > 0,
        "sibling_invocation": len(hard_calls) > 0,
        "router_node": len(router_nodes) > 0,
        "parent_mediated_dataflow": parent_mediated,
        "ambiguous_direct_dataflow": len(ambiguous_calls) > 0,
        "router_nodes": router_nodes,
        "hard_routing_calls": [{"from": s, "to": d} for s, d in hard_calls],
        "ambiguous_calls": [{"from": s, "to": d} for s, d in ambiguous_calls],
    }, evidence


# ========================================================================
# Dangling / source classification (identical to conservation rejudge)
# ========================================================================

def classify_source_v2(source_str, child_name, child, parent_case):
    if not source_str:
        return "dangling_input", "Empty source"
    s = source_str.strip()
    s_lower = s.lower()
    parent_node = parent_case["node"]
    parent_input_names = set()
    for inp in parent_node.inputs:
        parent_input_names.add(inp.name.lower())
    parent_input_names.update(["command", "order_data", "message_data", "build_request", "patient_data", "pipeline_request"])
    parent_gv_names = set()
    for gv in parent_node.global_vars:
        var = gv.variable if hasattr(gv, 'variable') else gv.get("variable", "")
        parent_gv_names.add(var.lower())
    parent_ds_names = set()
    for ds in parent_node.data_sources:
        name = ds.name if hasattr(ds, 'name') else ds.get("name", "")
        parent_ds_names.add(name.lower())
    child_resources = set()
    for gv in child.get("global_vars", []):
        var = gv.get("variable", gv.get("var", ""))
        if var: child_resources.add(var.lower())
    for do in child.get("data_operations", []):
        src = do.get("source_name", "")
        if src: child_resources.add(src.lower())
    for rc in child.get("requested_capabilities", []):
        if rc: child_resources.add(rc.lower())
    parent_patterns = [r"^parent input\b", r"^parent$", r"^parent input\.", r"^parent\b", r"^known parent input", r"\bparent input\b"]
    for pat in parent_patterns:
        if re.search(pat, s, re.IGNORECASE):
            return "parent_source", f"Matches parent pattern: {pat}"
    for pname in parent_input_names:
        if pname in s_lower:
            return "parent_source", f"References parent input '{pname}'"
    prev_child_patterns = [r"^previous child", r"\boutput\b", r"^[A-Z]\w+ output", r"^[A-Z]\w+\.", r"^Child\w+"]
    for pat in prev_child_patterns:
        if re.search(pat, s, re.IGNORECASE):
            return "previous_child_output_source", f"Matches child output pattern: {pat}"
    for gvname in parent_gv_names:
        if gvname in s_lower:
            return "resource_source", f"References parent global var '{gvname}'"
    for dsname in parent_ds_names:
        if dsname in s_lower:
            return "resource_source", f"References parent data source '{dsname}'"
    if "internal leaf access" in s_lower:
        if child_resources:
            return "internal_leaf_source", "Child has resource declarations"
        return "ambiguous_source", "internal leaf access but no child resource declarations"
    if "global variable" in s_lower:
        if parent_gv_names or parent_ds_names:
            return "resource_source", "global variable with known parent resources"
        return "ambiguous_source", "global variable without known parent resources"
    const_patterns = [r"^constant", r"^config", r"^default", r"^generated"]
    for pat in const_patterns:
        if re.search(pat, s, re.IGNORECASE):
            return "constant_source", f"Matches constant pattern: {pat}"
    if "data store" in s_lower or "store" in s_lower or "access" in s_lower:
        return "resource_source", "References data store"
    for gvname in parent_gv_names:
        if gvname in s_lower:
            return "resource_source", f"References parent resource '{gvname}'"
    for dsname in parent_ds_names:
        if dsname in s_lower:
            return "resource_source", f"References parent data source '{dsname}'"
    return "ambiguous_source", f"No matching pattern for: {s[:100]}"


def judge_dangling_v2(children, parent_case, use_inputs_field=True):
    results = []
    for c in children:
        name = c.get("name", "")
        inputs = c.get("inputs", []) if use_inputs_field else c.get("inputs", c.get("semantic_inputs", []))
        for inp in inputs:
            source = inp.get("source", "")
            inp_name = inp.get("name", "")
            source_class, evidence_reason = classify_source_v2(source, name, c, parent_case)
            results.append({"child": name, "input": inp_name, "source": source,
                            "source_class": source_class, "is_hard_dangling": source_class == "dangling_input",
                            "evidence": evidence_reason})
    hard_dangling = [r for r in results if r["is_hard_dangling"]]
    ambiguous = [r for r in results if r["source_class"] == "ambiguous_source"]
    return {"total_inputs": len(results), "hard_dangling_count": len(hard_dangling),
            "ambiguous_source_count": len(ambiguous), "hard_dangling": hard_dangling,
            "ambiguous_sources": ambiguous, "all_classifications": results}


# ========================================================================
# Resource coverage judge (identical to conservation rejudge)
# ========================================================================

def normalize_op(op):
    op = op.lower().strip()
    if op in ("read_write", "read+write"): return "read_write"
    if op in ("read", "query", "get", "list"): return "read"
    if op in ("write", "update", "mutate", "create", "insert", "delete"): return "write"
    return op


def normalize_resource_name(name):
    name = name.lower().strip()
    mapping = {"orders_db": "orders", "orders_store": "orders", "inventory_store": "inventory",
               "payments_db": "payments", "messages_store": "messages", "channels_store": "channels"}
    return mapping.get(name, name)


def judge_resource_coverage_v2(children, parent_case):
    parent_node = parent_case["node"]
    parent_resources = {}
    for gv in parent_node.global_vars:
        var = gv.variable if hasattr(gv, 'variable') else gv.get("variable", "")
        op = normalize_op(gv.op if hasattr(gv, 'op') else gv.get("op", "read"))
        nvar = normalize_resource_name(var)
        parent_resources.setdefault(nvar, set()).add(op)
    for ds in parent_node.data_sources:
        name = ds.name if hasattr(ds, 'name') else ds.get("name", "")
        access = ds.access if hasattr(ds, 'access') else ds.get("access", "read_write")
        op = normalize_op(access)
        nname = normalize_resource_name(name)
        parent_resources.setdefault(nname, set()).add(op)
    child_resources = {}
    all_child_vars = {}
    for c in children:
        name = c.get("name", "")
        child_resources[name] = set()
        for gv in c.get("global_vars", []):
            var = gv.get("variable", gv.get("var", ""))
            op = normalize_op(gv.get("op", gv.get("operation_type", "read")))
            nvar = normalize_resource_name(var)
            child_resources[name].add((nvar, op))
            all_child_vars.setdefault(nvar, set()).add(op)
        for do in c.get("data_operations", []):
            src = do.get("source_name", "")
            op = normalize_op(do.get("operation_type", "read"))
            if src:
                nsrc = normalize_resource_name(src)
                child_resources[name].add((nsrc, op))
                all_child_vars.setdefault(nsrc, set()).add(op)
    subset_violations = []
    parent_var_names = set(parent_resources.keys())
    for c in children:
        cname = c.get("name", "")
        for gv in c.get("global_vars", []):
            var = gv.get("variable", gv.get("var", ""))
            nvar = normalize_resource_name(var)
            if nvar and nvar not in parent_var_names:
                subset_violations.append({"child": cname, "variable": var,
                                          "reason": f"Variable '{var}' not in parent globals/data_sources"})
    coverage_gaps = []
    for var, required_ops in parent_resources.items():
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
                coverage_gaps.append({"variable": var, "required_op": req_op,
                                      "child_ops": list(child_ops),
                                      "reason": f"No child covers {var}:{req_op}"})
    ambiguous_resources = []
    for c in children:
        cname = c.get("name", "")
        for rc in c.get("requested_capabilities", []):
            if rc and "." in rc:
                resource_part = rc.split(".")[0]
                nres = normalize_resource_name(resource_part)
                if nres not in parent_var_names:
                    ambiguous_resources.append({"child": cname, "capability": rc,
                                                "reason": f"Requested capability '{rc}' not clearly mapped to parent resource"})
    return {"parent_resources": {k: list(v) for k, v in parent_resources.items()},
            "subset_violations": subset_violations, "coverage_gaps": coverage_gaps,
            "ambiguous_resources": ambiguous_resources,
            "child_resources": {k: list(v) for k, v in child_resources.items()},
            "child_resource_union": {k: list(v) for k, v in all_child_vars.items()}}


# ========================================================================
# Stage3 drift and false self-check
# ========================================================================

def check_stage3_drift(stage1, stage2, merged_children):
    """Check if Stage3 preserved Stage1 child identity and Stage2 interfaces."""
    s1_names = [c.get("name", "") for c in stage1.get("children", [])]
    merged_names = [c.get("name", "") for c in merged_children]

    drift_issues = []
    if s1_names != merged_names:
        drift_issues.append(f"child_names_changed: s1={s1_names} merged={merged_names}")

    # Check Stage2 interface preservation
    s2_map = {c.get("name", ""): c for c in stage2.get("children", [])}
    for c in merged_children:
        cname = c.get("name", "")
        if cname not in s2_map:
            continue
        s2c = s2_map[cname]
        for field in ("inputs", "outputs", "signature"):
            s2_val = s2c.get(field)
            merged_val = c.get(field)
            if s2_val is not None and merged_val != s2_val:
                drift_issues.append(f"{cname}.{field}: Stage2 != merged")

    return {"stage3_interface_drift": len(drift_issues) > 0, "drift_issues": drift_issues,
            "s1_names": s1_names, "merged_names": merged_names}


def check_false_self_check(governance_notes, coverage_gaps):
    """If governance_notes claims coverage but judge found gaps, count as false self-check."""
    if not governance_notes or not isinstance(governance_notes, str):
        return 0
    notes_lower = governance_notes.lower()
    if not coverage_gaps:
        return 0
    claim_phrases = ["all covered", "all rows covered", "every row covered",
                     "conservation satisfied", "all global vars covered",
                     "all parent global", "verified", "no gaps", "complete coverage"]
    for phrase in claim_phrases:
        if phrase in notes_lower:
            return len(coverage_gaps)
    return 0


# ========================================================================
# Field completeness
# ========================================================================

REQUIRED_FIELDS = ["name", "purpose", "behavior", "inputs", "outputs", "signature",
                   "global_vars", "data_operations", "constraints", "acceptance_criteria",
                   "traceability", "node_type"]


def check_missing_fields(children):
    missing = []
    for c in children:
        cname = c.get("name", "?")
        for f in REQUIRED_FIELDS:
            if f not in c or c[f] is None:
                missing.append(f"{cname}:{f}")
    return missing


# ========================================================================
# Per-repeat judge
# ========================================================================

def judge_repeat(repeat_dir, case_name, trial_idx, repeat_idx, parent_case):
    stage1_file = repeat_dir / "stage1.json"
    stage2_file = repeat_dir / "stage2.json"
    stage3_file = repeat_dir / "stage3.json"
    merged_file = repeat_dir / "merged_node.json"
    result_file = repeat_dir / "result.json"

    if not merged_file.exists() or not stage3_file.exists():
        return {"error": "missing files", "case": case_name, "trial": trial_idx, "repeat": repeat_idx}

    stage1 = parse_json_file(stage1_file) if stage1_file.exists() else {}
    stage2 = parse_json_file(stage2_file) if stage2_file.exists() else {}
    stage3 = parse_json_file(stage3_file)
    merged = parse_json_file(merged_file)
    old_result = {}
    if result_file.exists():
        with open(result_file, "r", encoding="utf-8") as f:
            old_result = json.load(f)

    if isinstance(merged, list):
        merged_children = merged
    elif isinstance(merged, dict):
        merged_children = merged.get("children", merged)
    else:
        merged_children = []

    stage1_children = stage1.get("children", [])
    dataflow = stage1.get("dataflow_sketch", stage1.get("dataflow_edges", []))
    rationale = stage1.get("decomposition_rationale", "")
    expected_range = parent_case.get("expected_children_range", (2, 10))

    # Routing (from frozen Stage1)
    routing_result, routing_evidence = judge_routing(stage1_children, dataflow, rationale)

    # Stage3 drift
    drift_result = check_stage3_drift(stage1, stage2, merged_children)

    # Dangling (from merged)
    dangling_result = judge_dangling_v2(merged_children, parent_case, use_inputs_field=True)

    # Resource coverage (from merged)
    resource_result = judge_resource_coverage_v2(merged_children, parent_case)

    # Missing fields
    missing_fields = check_missing_fields(merged_children)

    # Child count
    n_children = len(merged_children)
    child_count_viol = n_children < expected_range[0] or n_children > expected_range[1]

    # False self-check
    governance_notes = stage3.get("governance_notes", "")
    false_self_check = check_false_self_check(governance_notes, resource_result["coverage_gaps"])

    return {
        "condition": "three_stage", "case": case_name, "trial": trial_idx, "repeat": repeat_idx,
        "n_children": n_children, "child_names": [c.get("name", "") for c in merged_children],
        "routing": routing_result,
        "stage3_drift": drift_result,
        "dangling": {"hard_dangling_count": dangling_result["hard_dangling_count"],
                     "ambiguous_source_count": dangling_result["ambiguous_source_count"],
                     "hard_dangling": dangling_result["hard_dangling"],
                     "ambiguous_sources": dangling_result["ambiguous_sources"]},
        "resource": {"subset_violations": resource_result["subset_violations"],
                     "coverage_gaps": resource_result["coverage_gaps"],
                     "ambiguous_resources": resource_result["ambiguous_resources"],
                     "parent_resources": resource_result["parent_resources"],
                     "child_resource_union": resource_result["child_resource_union"]},
        "missing_required_fields": missing_fields[:20],
        "missing_required_fields_count": len(missing_fields),
        "governance_notes_excerpt": governance_notes[:300],
        "false_self_check_count": false_self_check,
        "child_count_violation": child_count_viol,
        "expected_children_range": expected_range,
        "parse_error": False,
        "evidence": routing_evidence,
    }


# ========================================================================
# Report generation
# ========================================================================

def generate_report(results):
    metrics = results["metrics"]
    trials = results["trials"]
    n_total = len(trials)

    # Load v2 for comparison
    v2_metrics = {}
    v2_file = V2_DIR / "results.json"
    if v2_file.exists():
        with open(v2_file, "r", encoding="utf-8") as f:
            v2_data = json.load(f)
        v2_metrics = v2_data.get("metrics_by_condition", {}).get("three_stage", {})

    lines = [
        "# Exp03 Fixed-Input Stage3 Conservation Rejudge Report",
        "",
        "Model: `deepseek-v4-flash`",
        "",
        "## Experiment Description",
        "",
        "This experiment freezes Stage1 and Stage2 from the original Exp03 three_stage run",
        "and reruns only Stage3 with the conservation prompt. Each frozen input is repeated",
        f"multiple times to measure Stage3 stochasticity. Total repeats: {n_total}.",
        "",
        "The judge uses the same v2 logic: routing from frozen Stage1, resource coverage",
        "from merged_node, parent globals from decomposer_cases. Additionally checks",
        "stage3_interface_drift and governance_notes false self-check.",
        "",
        "## Aggregate Metrics\n",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total repeats | {n_total} |",
        f"| Parse errors | {metrics['parse_errors']} |",
        f"| Stage3 interface drift | {metrics['stage3_drift']} |",
        f"| Hard routing (frozen Stage1 context) | {metrics['hard_routing']} |",
        f"| Hard dangling | {metrics['hard_dangling']} |",
        f"| Ambiguous source | {metrics['ambiguous_source']} |",
        f"| Resource coverage gap (total) | {metrics['resource_coverage_gap']} |",
        f"| Global var subset violation | {metrics['gv_subset_violation']} |",
        f"| Missing required fields | {metrics['missing_fields']} |",
        f"| False self-check | {metrics['false_self_check']} |",
        f"| Child count violation | {metrics['child_count_violation']} |",
        "",
    ]

    # Comparison with v2
    if v2_metrics:
        lines.append("## Comparison with V2 Baseline (three_stage, original full-pipeline)\n")
        lines.append("| Metric | V2 Baseline (15 trials) | Fixed-Input Conservation | Notes |")
        lines.append("|--------|------------------------|-------------------------|-------|")
        v2_rg = v2_metrics.get("resource_coverage_gap", "N/A")
        new_rg = metrics["resource_coverage_gap"]
        delta_rg = new_rg - v2_rg if isinstance(v2_rg, int) else "N/A"
        lines.append(f"| resource_coverage_gap | {v2_rg} | {new_rg} | delta={delta_rg} |")
        v2_hr = v2_metrics.get("hard_routing", "N/A")
        lines.append(f"| hard_routing | {v2_hr} | {metrics['hard_routing']} | frozen context |")
        v2_sd = v2_metrics.get("stage_drift", "N/A")
        lines.append(f"| stage_drift | {v2_sd} | {metrics['stage3_drift']} | |")
        v2_hd = v2_metrics.get("hard_dangling_input", "N/A")
        lines.append(f"| hard_dangling | {v2_hd} | {metrics['hard_dangling']} | |")
        v2_lrf = v2_metrics.get("llm_composition_review_failure", "N/A")
        lines.append(f"| llm_review_fail | {v2_lrf} | N/A | not measured in this experiment |")
        lines.append("")

    # Per-case breakdown
    lines.append("## Per-Case Breakdown\n")
    lines.append("| Case | Repeats | Drift | Hard Rout | Hard Dang | Ambig Src | Res Gaps | False Self-Check | Child Count Viol |")
    lines.append("|------|---------|-------|-----------|-----------|-----------|----------|-----------------|-----------------|")
    for case_name in CASES:
        ct = [t for t in trials if t.get("case") == case_name and not t.get("parse_error") and not t.get("error")]
        if not ct: continue
        n = len(ct)
        dr = sum(1 for t in ct if t.get("stage3_drift", {}).get("stage3_interface_drift"))
        hr = sum(1 for t in ct if t.get("routing", {}).get("hard_routing"))
        hd = sum(t.get("dangling", {}).get("hard_dangling_count", 0) for t in ct)
        am = sum(t.get("dangling", {}).get("ambiguous_source_count", 0) for t in ct)
        rg = sum(len(t.get("resource", {}).get("coverage_gaps", [])) for t in ct)
        fs = sum(t.get("false_self_check_count", 0) for t in ct)
        cc = sum(1 for t in ct if t.get("child_count_violation"))
        lines.append(f"| {case_name} | {n} | {dr} | {hr} | {hd} | {am} | {rg} | {fs} | {cc} |")
    lines.append("")

    # Per-variable gap distribution
    lines.append("## Per-Variable Gap Distribution\n")
    gap_counter = {}
    for t in trials:
        for gap in t.get("resource", {}).get("coverage_gaps", []):
            key = f"{gap['variable']}:{gap['required_op']}"
            gap_counter[key] = gap_counter.get(key, 0) + 1
    if gap_counter:
        lines.append("| Variable:Op | Gap Count | Repeats Affected |")
        lines.append("|-------------|-----------|-----------------|")
        for key, count in sorted(gap_counter.items(), key=lambda x: -x[1]):
            lines.append(f"| {key} | {count} | {count}/{n_total} |")
    else:
        lines.append("No resource coverage gaps found.")
    lines.append("")

    # Old gap fixed / new gap introduced analysis
    if v2_metrics and v2_file.exists():
        lines.append("## Old Gap Fixed / New Gap Introduced\n")
        v2_gaps_by_case = {}
        with open(v2_file, "r", encoding="utf-8") as f:
            v2_data = json.load(f)
        for t in v2_data.get("trials", []):
            if t.get("condition") != "three_stage":
                continue
            case = t.get("case", "")
            for gap in t.get("resource", {}).get("coverage_gaps", []):
                key = f"{gap['variable']}:{gap['required_op']}"
                v2_gaps_by_case.setdefault(case, set()).add(key)

        new_gaps_by_case = {}
        for t in trials:
            if t.get("error") or t.get("parse_error"):
                continue
            case = t.get("case", "")
            for gap in t.get("resource", {}).get("coverage_gaps", []):
                key = f"{gap['variable']}:{gap['required_op']}"
                new_gaps_by_case.setdefault(case, set()).add(key)

        all_fixed = []
        all_new = []
        for case_name in CASES:
            v2_keys = v2_gaps_by_case.get(case_name, set())
            new_keys = new_gaps_by_case.get(case_name, set())
            fixed = v2_keys - new_keys
            introduced = new_keys - v2_keys
            if fixed:
                all_fixed.extend([(case_name, k) for k in fixed])
            if introduced:
                all_new.extend([(case_name, k) for k in introduced])

        if all_fixed:
            lines.append(f"### Old gaps fixed ({len(all_fixed)}):\n")
            for case, key in all_fixed:
                lines.append(f"- {case}: {key}")
            lines.append("")
        else:
            lines.append("### No old gaps fixed.\n")

        if all_new:
            lines.append(f"### New gaps introduced ({len(all_new)}):\n")
            for case, key in all_new:
                lines.append(f"- {case}: {key}")
            lines.append("")
        else:
            lines.append("### No new gaps introduced.\n")

    # Verdict
    lines.append("## Verdict\n")
    if metrics["parse_errors"] > 0:
        lines.append(f"- **FAIL**: {metrics['parse_errors']} parse errors")
    elif metrics["stage3_drift"] > 0:
        lines.append(f"- **FAIL**: {metrics['stage3_drift']} stage3 interface drift")
    elif metrics["resource_coverage_gap"] > 0:
        lines.append(f"- **FAIL**: {metrics['resource_coverage_gap']} resource coverage gaps remain across {n_total} repeats")
        lines.append(f"  - Global state conservation is an architectural invariant; persistent gaps indicate")
        lines.append(f"    the conservation prompt does not reliably fix resource allocation.")
    else:
        lines.append(f"- **PASS**: zero parse errors, zero drift, zero resource coverage gaps")
    lines.append("")
    lines.append("**This verdict is deterministic rejudge only; actual codegen composability remains unverified.**")
    lines.append("")

    # Manual sampling
    lines.append("## Manual Sampling Notes\n")
    # Drift cases
    drift_trials = [t for t in trials if t.get("stage3_drift", {}).get("stage3_interface_drift")]
    if drift_trials:
        lines.append("### Stage3 Interface Drift\n")
        for t in drift_trials[:5]:
            lines.append(f"- **{t.get('case')}/trial_{t.get('trial', 0):02d}/repeat_{t.get('repeat', 0):02d}**: {t.get('stage3_drift', {}).get('drift_issues', [])}")
        lines.append("")

    # Gap cases - sample one per case
    gap_trials = [t for t in trials if len(t.get("resource", {}).get("coverage_gaps", [])) > 0]
    if gap_trials:
        lines.append("### Resource Gap Patterns\n")
        seen_cases = set()
        for t in gap_trials:
            if t["case"] in seen_cases:
                continue
            seen_cases.add(t["case"])
            lines.append(f"#### {t['case']}/trial_{t.get('trial', 0):02d}/repeat_{t.get('repeat', 0):02d}\n")
            lines.append(f"- Child names: {t.get('child_names', [])}")
            res = t.get("resource", {})
            lines.append(f"- Child resource union: {res.get('child_resource_union', {})}")
            lines.append(f"- Gaps:")
            for gap in res.get("coverage_gaps", []):
                lines.append(f"  - {gap['variable']}:{gap['required_op']} — {gap['reason']} (child ops: {gap.get('child_ops', [])})")
            gn = t.get("governance_notes_excerpt", "")
            if gn:
                lines.append(f"- Governance notes (excerpt): {gn}")
            lines.append("")

    return "\n".join(lines)


# ========================================================================
# Main
# ========================================================================

def main():
    all_trials = []

    three_dir = INPUT_DIR / "three_stage"
    if not three_dir.exists():
        print(f"ERROR: Input directory not found: {three_dir}")
        return 1

    for case_name in CASES:
        case_dir = three_dir / case_name
        if not case_dir.exists():
            print(f"  Skipping {case_name}: directory not found")
            continue
        parent_case = CASE_BY_NAME.get(case_name)
        if not parent_case:
            print(f"  WARNING: No parent case for {case_name}")
            continue
        for trial_dir in sorted(case_dir.iterdir()):
            if not trial_dir.is_dir() or not trial_dir.name.startswith("trial_"):
                continue
            trial_idx = int(trial_dir.name.split("_")[1])
            for repeat_dir in sorted(trial_dir.iterdir()):
                if not repeat_dir.is_dir() or not repeat_dir.name.startswith("repeat_"):
                    continue
                repeat_idx = int(repeat_dir.name.split("_")[1])
                result = judge_repeat(repeat_dir, case_name, trial_idx, repeat_idx, parent_case)
                if result:
                    all_trials.append(result)

    # Aggregate metrics
    valid_trials = [t for t in all_trials if not t.get("parse_error") and not t.get("error")]
    n = len(valid_trials)
    metrics = {
        "total": len(all_trials),
        "valid": n,
        "parse_errors": sum(1 for t in all_trials if t.get("parse_error") or t.get("error")),
        "stage3_drift": sum(1 for t in valid_trials if t.get("stage3_drift", {}).get("stage3_interface_drift")),
        "hard_routing": sum(1 for t in valid_trials if t.get("routing", {}).get("hard_routing")),
        "hard_dangling": sum(t.get("dangling", {}).get("hard_dangling_count", 0) for t in valid_trials),
        "ambiguous_source": sum(t.get("dangling", {}).get("ambiguous_source_count", 0) for t in valid_trials),
        "resource_coverage_gap": sum(len(t.get("resource", {}).get("coverage_gaps", [])) for t in valid_trials),
        "gv_subset_violation": sum(len(t.get("resource", {}).get("subset_violations", [])) for t in valid_trials),
        "missing_fields": sum(t.get("missing_required_fields_count", 0) for t in valid_trials),
        "false_self_check": sum(t.get("false_self_check_count", 0) for t in valid_trials),
        "child_count_violation": sum(1 for t in valid_trials if t.get("child_count_violation")),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {
        "model": "deepseek-v4-flash",
        "version": "fixed_stage3_conservation",
        "description": "Exp03 fixed-input Stage3 conservation rejudge: routing from frozen Stage1, resource from merged_node, parent globals from decomposer_cases, with stage3 drift and false self-check",
        "metrics": metrics,
        "trials": all_trials,
    }
    with open(OUTPUT_DIR / "results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    report = generate_report(results)
    with open(OUTPUT_DIR / "report.md", "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Fixed-input Stage3 conservation rejudge complete. Output: {OUTPUT_DIR}")
    print(f"  Total: {metrics['total']}, Valid: {metrics['valid']}, Parse errors: {metrics['parse_errors']}")
    print(f"  Stage3 drift: {metrics['stage3_drift']}")
    print(f"  Hard routing: {metrics['hard_routing']}")
    print(f"  Resource coverage gaps: {metrics['resource_coverage_gap']}")
    print(f"  False self-check: {metrics['false_self_check']}")
    print(f"  Child count violation: {metrics['child_count_violation']}")


if __name__ == "__main__":
    main()
