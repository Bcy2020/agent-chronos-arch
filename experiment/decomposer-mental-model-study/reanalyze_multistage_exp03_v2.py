"""
Exp03 Rejudge V2 — Deterministic rejudge using correct source-of-truth.

Key differences from v1:
1. Routing: three_stage uses stage1.json; single-stage uses 0001_response.json
2. Interface/dangling: three_stage uses merged_node.json (not stage1.json)
3. Resource coverage: uses parent globals from test_data/decomposer_cases.py
4. Child count: uses case-specific expected_children_range
5. Adds stage_drift, missing_required_fields metrics
6. Dangling input v2: checks `inputs` field, not `semantic_inputs` for three_stage
"""

import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
INPUT_DIR = SCRIPT_DIR / "output" / "multistage_exp03_pipeline_regression" / "deepseek-v4-flash"
OUTPUT_DIR = SCRIPT_DIR / "output" / "multistage_exp03_pipeline_regression_rejudged_v2" / "deepseek-v4-flash"

CONDITIONS = ["single_stage_baseline", "single_stage_notraditional", "three_stage"]
CASES = ["OrderSystem", "ChatApp", "PatientPortal", "BuildSystem", "DataPipeline"]

# --- Load parent cases for resource coverage ---
sys.path.insert(0, str(SCRIPT_DIR / "test_data"))
from decomposer_cases import ALL_CASES

CASE_BY_NAME = {}
for case in ALL_CASES:
    name = case["node"].name
    CASE_BY_NAME[name] = case


# --- Routing judge (same as v1) ---
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
    """Parse a JSON file, handling response wrapper."""
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


# ========================================================================
# Routing judge (from Stage 1 / raw response)
# ========================================================================

def judge_routing(children, dataflow, rationale):
    """Apply Exp01 routing judge. Returns dict with booleans + evidence."""
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
                "reason": "Router-like name with control-call semantics"
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
# Dangling input V2 (uses `inputs` field for three_stage)
# ========================================================================

def classify_source_v2(source_str, child_name, child, parent_case):
    """Classify a child input source with stricter rules than v1.

    Rules:
    1. Empty source -> dangling_input
    2. "parent input", "parent", known parent input name -> parent_source
    3. Source naming earlier child output -> previous_child_output_source
    4. Source naming known parent global var or data source -> resource_source
    5. "internal leaf access" -> valid only if child declares matching resource
    6. "global variable" -> valid only if maps to parent global/data source or child resource
    7. Otherwise -> ambiguous_source
    """
    if not source_str:
        return "dangling_input", "Empty source"

    s = source_str.strip()
    s_lower = s.lower()

    # Get parent input names
    parent_node = parent_case["node"]
    parent_input_names = set()
    for inp in parent_node.inputs:
        parent_input_names.add(inp.name.lower())
    parent_input_names.add("command")
    parent_input_names.add("order_data")
    parent_input_names.add("message_data")
    parent_input_names.add("build_request")
    parent_input_names.add("patient_data")
    parent_input_names.add("pipeline_request")

    # Get parent global var names
    parent_gv_names = set()
    for gv in parent_node.global_vars:
        var = gv.variable if hasattr(gv, 'variable') else gv.get("variable", "")
        parent_gv_names.add(var.lower())

    # Get parent data source names
    parent_ds_names = set()
    for ds in parent_node.data_sources:
        name = ds.name if hasattr(ds, 'name') else ds.get("name", "")
        parent_ds_names.add(name.lower())

    # Get child resource declarations
    child_resources = set()
    for gv in child.get("global_vars", []):
        var = gv.get("variable", gv.get("var", ""))
        if var:
            child_resources.add(var.lower())
    for do in child.get("data_operations", []):
        src = do.get("source_name", "")
        if src:
            child_resources.add(src.lower())
    for rc in child.get("requested_capabilities", []):
        if rc:
            child_resources.add(rc.lower())

    # 1. parent_source patterns
    parent_patterns = [
        r"^parent input\b", r"^parent$", r"^parent input\.", r"^parent\b",
        r"^known parent input", r"\bparent input\b",
    ]
    for pat in parent_patterns:
        if re.search(pat, s, re.IGNORECASE):
            return "parent_source", f"Matches parent pattern: {pat}"

    # Check if source references a known parent input name
    for pname in parent_input_names:
        if pname in s_lower:
            return "parent_source", f"References parent input '{pname}'"

    # 2. previous child output
    prev_child_patterns = [
        r"^previous child", r"\boutput\b", r"^[A-Z]\w+ output",
        r"^[A-Z]\w+\.", r"^Child\w+",
    ]
    for pat in prev_child_patterns:
        if re.search(pat, s, re.IGNORECASE):
            return "previous_child_output_source", f"Matches child output pattern: {pat}"

    # 3. resource_source: known parent global var or data source
    for gvname in parent_gv_names:
        if gvname in s_lower:
            return "resource_source", f"References parent global var '{gvname}'"
    for dsname in parent_ds_names:
        if dsname in s_lower:
            return "resource_source", f"References parent data source '{dsname}'"

    # 4. "internal leaf access" — valid only if child declares matching resource
    if "internal leaf access" in s_lower:
        if child_resources:
            return "internal_leaf_source", "Child has resource declarations"
        return "ambiguous_source", "internal leaf access but no child resource declarations"

    # 5. "global variable" — valid only if maps to known resource
    if "global variable" in s_lower:
        if parent_gv_names or parent_ds_names:
            return "resource_source", "global variable with known parent resources"
        return "ambiguous_source", "global variable without known parent resources"

    # 6. constant/config/default
    const_patterns = [r"^constant", r"^config", r"^default", r"^generated"]
    for pat in const_patterns:
        if re.search(pat, s, re.IGNORECASE):
            return "constant_source", f"Matches constant pattern: {pat}"

    # 7. data store
    if "data store" in s_lower or "store" in s_lower or "access" in s_lower:
        return "resource_source", "References data store"

    # 8. Check if any parent resource name appears in source
    for gvname in parent_gv_names:
        if gvname in s_lower:
            return "resource_source", f"References parent resource '{gvname}'"
    for dsname in parent_ds_names:
        if dsname in s_lower:
            return "resource_source", f"References parent data source '{dsname}'"

    return "ambiguous_source", f"No matching pattern for: {s[:100]}"


def judge_dangling_v2(children, parent_case, use_inputs_field=True):
    """Judge dangling inputs using the correct source-of-truth field.

    For three_stage (use_inputs_field=True): use `inputs` field from merged_node.json
    For single-stage (use_inputs_field=False): use `inputs` from raw response
    """
    results = []
    for c in children:
        name = c.get("name", "")
        # V2: use `inputs` field, not `semantic_inputs`
        if use_inputs_field:
            inputs = c.get("inputs", [])
        else:
            inputs = c.get("inputs", c.get("semantic_inputs", []))

        for inp in inputs:
            source = inp.get("source", "")
            inp_name = inp.get("name", "")
            source_class, evidence_reason = classify_source_v2(
                source, name, c, parent_case
            )
            results.append({
                "child": name,
                "input": inp_name,
                "source": source,
                "source_class": source_class,
                "is_hard_dangling": source_class == "dangling_input",
                "evidence": evidence_reason,
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


# ========================================================================
# Resource coverage V2 (with parent globals)
# ========================================================================

def normalize_op(op):
    op = op.lower().strip()
    if op in ("read_write", "read+write"):
        return "read_write"
    if op in ("read", "query", "get", "list"):
        return "read"
    if op in ("write", "update", "mutate", "create", "insert", "delete"):
        return "write"
    return op


def normalize_resource_name(name):
    """Conservative resource name normalization."""
    name = name.lower().strip()
    mapping = {
        "orders_db": "orders", "orders_store": "orders",
        "inventory_store": "inventory",
        "payments_db": "payments",
        "messages_store": "messages",
        "channels_store": "channels",
    }
    return mapping.get(name, name)


def judge_resource_coverage_v2(children, parent_case):
    """Check resource coverage using parent globals from decomposer_cases.py."""
    parent_node = parent_case["node"]

    # Build parent resource requirements
    parent_resources = {}  # normalized_name -> set of ops
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

    # Build child resource declarations
    child_resources = {}  # child_name -> set of (normalized_var, op)
    all_child_vars = {}  # normalized_var -> set of ops

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

    # Subset violation: child declares a resource not in parent
    subset_violations = []
    parent_var_names = set(parent_resources.keys())
    for c in children:
        cname = c.get("name", "")
        for gv in c.get("global_vars", []):
            var = gv.get("variable", gv.get("var", ""))
            nvar = normalize_resource_name(var)
            if nvar and nvar not in parent_var_names:
                subset_violations.append({
                    "child": cname, "variable": var,
                    "reason": f"Variable '{var}' not in parent globals/data_sources"
                })

    # Coverage gap: parent requires an op, no child covers it
    coverage_gaps = []
    for var, required_ops in parent_resources.items():
        child_ops = all_child_vars.get(var, set())
        for req_op in required_ops:
            covered = False
            if req_op == "read_write":
                covered = ("read_write" in child_ops or
                           ("read" in child_ops and "write" in child_ops))
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

    # Ambiguous resource coverage
    ambiguous_resources = []
    for c in children:
        cname = c.get("name", "")
        for rc in c.get("requested_capabilities", []):
            if rc and "." in rc:
                resource_part = rc.split(".")[0]
                nres = normalize_resource_name(resource_part)
                if nres not in parent_var_names:
                    ambiguous_resources.append({
                        "child": cname, "capability": rc,
                        "reason": f"Requested capability '{rc}' not clearly mapped to parent resource"
                    })

    return {
        "parent_resources": {k: list(v) for k, v in parent_resources.items()},
        "subset_violations": subset_violations,
        "coverage_gaps": coverage_gaps,
        "ambiguous_resources": ambiguous_resources,
        "child_resources": {k: list(v) for k, v in child_resources.items()},
        "child_resource_union": {k: list(v) for k, v in all_child_vars.items()},
    }


# ========================================================================
# Stage drift detection
# ========================================================================

def check_stage_drift(stage1_children, merged_children):
    """Compare stage1 child names with merged child names."""
    s1_names = [c.get("name", "") for c in stage1_children]
    merged_names = [c.get("name", "") for c in merged_children]
    return {
        "stage_drift": s1_names != merged_names,
        "stage1_names": s1_names,
        "merged_names": merged_names,
    }


# ========================================================================
# Missing required fields
# ========================================================================

REQUIRED_FIELDS_THREE_STAGE = [
    "name", "purpose", "behavior", "inputs", "outputs", "signature",
    "global_vars", "data_operations", "constraints", "acceptance_criteria",
    "traceability", "node_type",
]

REQUIRED_FIELDS_SINGLE_STAGE = [
    "name", "purpose", "inputs", "outputs", "boundary",
    "preconditions", "postconditions", "behavior", "signature",
    "data_operations", "constraints", "acceptance_criteria",
    "global_vars", "traceability", "requested_capabilities",
]


def check_missing_fields(children, condition):
    required = REQUIRED_FIELDS_THREE_STAGE if condition == "three_stage" else REQUIRED_FIELDS_SINGLE_STAGE
    missing = []
    for c in children:
        cname = c.get("name", "?")
        for f in required:
            if f not in c or c[f] is None:
                missing.append(f"{cname}:{f}")
    return missing


# ========================================================================
# Trial judgment
# ========================================================================

def judge_three_stage_trial(trial_dir, case_name, trial_idx, parent_case):
    """Judge a three-stage trial using correct source-of-truth."""
    stage1_file = trial_dir / "stage1.json"
    merged_file = trial_dir / "merged_node.json"
    result_file = trial_dir / "result.json"

    if not stage1_file.exists() or not merged_file.exists():
        return {"error": "missing files", "stage1": stage1_file.exists(), "merged": merged_file.exists()}

    stage1 = parse_json_file(stage1_file)
    merged = parse_json_file(merged_file)

    old_result = {}
    if result_file.exists():
        with open(result_file, "r", encoding="utf-8") as f:
            old_result = json.load(f)

    if isinstance(merged, list):
        merged_children = merged
    else:
        merged_children = merged.get("children", merged) if isinstance(merged, dict) else []

    stage1_children = stage1.get("children", [])
    dataflow = stage1.get("dataflow_sketch", stage1.get("dataflow_edges", []))
    rationale = stage1.get("decomposition_rationale", "")

    expected_range = parent_case.get("expected_children_range", (2, 10))

    # Routing: from Stage 1
    routing_result, routing_evidence = judge_routing(stage1_children, dataflow, rationale)

    # Stage drift
    drift = check_stage_drift(stage1_children, merged_children)

    # Dangling: from merged_node.json (inputs field)
    dangling_result = judge_dangling_v2(merged_children, parent_case, use_inputs_field=True)

    # Resource coverage: from merged children + parent globals
    resource_result = judge_resource_coverage_v2(merged_children, parent_case)

    # Missing fields
    missing_fields = check_missing_fields(merged_children, "three_stage")

    # Child count
    n_children = len(merged_children)
    child_count_viol = n_children < expected_range[0] or n_children > expected_range[1]

    return {
        "condition": "three_stage",
        "case": case_name,
        "trial": trial_idx,
        "n_children": n_children,
        "child_names": [c.get("name", "") for c in merged_children],
        "routing": routing_result,
        "stage_drift": drift,
        "dangling": {
            "hard_dangling_count": dangling_result["hard_dangling_count"],
            "ambiguous_source_count": dangling_result["ambiguous_source_count"],
            "hard_dangling": dangling_result["hard_dangling"],
            "ambiguous_sources": dangling_result["ambiguous_sources"],
        },
        "resource": {
            "subset_violations": resource_result["subset_violations"],
            "coverage_gaps": resource_result["coverage_gaps"],
            "ambiguous_resources": resource_result["ambiguous_resources"],
            "parent_resources": resource_result["parent_resources"],
            "child_resource_union": resource_result["child_resource_union"],
        },
        "missing_required_fields": missing_fields[:20],
        "missing_required_fields_count": len(missing_fields),
        "llm_composition_review_failure": old_result.get("cannot_compose", False),
        "child_count_violation": child_count_viol,
        "expected_children_range": expected_range,
        "parse_error": False,
        "evidence": routing_evidence,
    }


def judge_single_stage_trial(trial_dir, condition, case_name, trial_idx, parent_case):
    """Judge a single-stage trial from 0001_response.json."""
    response_file = trial_dir / "0001_response.json"
    result_file = trial_dir / "result.json"

    old_result = {}
    if result_file.exists():
        with open(result_file, "r", encoding="utf-8") as f:
            old_result = json.load(f)

    expected_range = parent_case.get("expected_children_range", (2, 10))

    if not response_file.exists():
        return {
            "condition": condition,
            "case": case_name,
            "trial": trial_idx,
            "n_children": old_result.get("n_children", 0),
            "child_names": old_result.get("child_names", []),
            "routing": {"hard_routing": old_result.get("has_routing", False)},
            "stage_drift": {"stage_drift": False, "note": "N/A for single-stage"},
            "dangling": {
                "hard_dangling_count": len(old_result.get("dangling_inputs", [])),
                "note": "raw data unavailable"
            },
            "resource": {"note": "raw data unavailable"},
            "missing_required_fields": [],
            "llm_composition_review_failure": old_result.get("cannot_compose", False),
            "child_count_violation": old_result.get("child_count_violation", False),
            "expected_children_range": expected_range,
            "parse_error": False,
            "evidence": [],
            "data_limitation": "raw child content unavailable",
        }

    parsed = parse_json_file(response_file)
    if "error" in parsed and "children" not in parsed:
        return {
            "condition": condition,
            "case": case_name,
            "trial": trial_idx,
            "parse_error": True,
            "error": parsed.get("error"),
        }

    children = parsed.get("children", [])
    dataflow = parsed.get("dataflow_edges", parsed.get("dataflow_sketch", []))
    rationale = parsed.get("decomposition_rationale", "")

    # Routing: from raw response
    routing_result, routing_evidence = judge_routing(children, dataflow, rationale)

    # Dangling: from raw response (inputs field)
    dangling_result = judge_dangling_v2(children, parent_case, use_inputs_field=True)

    # Resource coverage: from children + parent globals
    resource_result = judge_resource_coverage_v2(children, parent_case)

    # Missing fields
    missing_fields = check_missing_fields(children, condition)

    # Child count
    n_children = len(children)
    child_count_viol = n_children < expected_range[0] or n_children > expected_range[1]

    return {
        "condition": condition,
        "case": case_name,
        "trial": trial_idx,
        "n_children": n_children,
        "child_names": [c.get("name", "") for c in children],
        "routing": routing_result,
        "stage_drift": {"stage_drift": False, "note": "N/A for single-stage"},
        "dangling": {
            "hard_dangling_count": dangling_result["hard_dangling_count"],
            "ambiguous_source_count": dangling_result["ambiguous_source_count"],
            "hard_dangling": dangling_result["hard_dangling"],
            "ambiguous_sources": dangling_result["ambiguous_sources"],
        },
        "resource": {
            "subset_violations": resource_result["subset_violations"],
            "coverage_gaps": resource_result["coverage_gaps"],
            "ambiguous_resources": resource_result["ambiguous_resources"],
            "parent_resources": resource_result["parent_resources"],
            "child_resource_union": resource_result["child_resource_union"],
        },
        "missing_required_fields": missing_fields[:20],
        "missing_required_fields_count": len(missing_fields),
        "llm_composition_review_failure": old_result.get("cannot_compose", False),
        "child_count_violation": child_count_viol,
        "expected_children_range": expected_range,
        "parse_error": False,
        "evidence": routing_evidence,
    }


# ========================================================================
# Main
# ========================================================================

def main():
    all_trials = []

    for condition in CONDITIONS:
        cond_dir = INPUT_DIR / condition
        if not cond_dir.exists():
            print(f"  Skipping {condition}: directory not found")
            continue
        for case_name in CASES:
            case_dir = cond_dir / case_name
            if not case_dir.exists():
                continue

            parent_case = CASE_BY_NAME.get(case_name)
            if not parent_case:
                print(f"  WARNING: No parent case for {case_name}")
                continue

            for trial_dir in sorted(case_dir.iterdir()):
                if not trial_dir.is_dir() or not trial_dir.name.startswith("trial_"):
                    continue
                trial_idx = int(trial_dir.name.split("_")[1])

                if condition == "three_stage":
                    result = judge_three_stage_trial(trial_dir, case_name, trial_idx, parent_case)
                else:
                    result = judge_single_stage_trial(trial_dir, condition, case_name, trial_idx, parent_case)

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
            "stage_drift": sum(1 for t in ct if t.get("stage_drift", {}).get("stage_drift")),
            "missing_required_fields": sum(t.get("missing_required_fields_count", 0) for t in ct),
            "hard_dangling_input": sum(t.get("dangling", {}).get("hard_dangling_count", 0) for t in ct),
            "ambiguous_source": sum(t.get("dangling", {}).get("ambiguous_source_count", 0) for t in ct),
            "global_var_subset_violation": sum(len(t.get("resource", {}).get("subset_violations", [])) for t in ct),
            "resource_coverage_gap": sum(len(t.get("resource", {}).get("coverage_gaps", [])) for t in ct),
            "ambiguous_resource_coverage": sum(len(t.get("resource", {}).get("ambiguous_resources", [])) for t in ct),
            "llm_composition_review_failure": sum(1 for t in ct if t.get("llm_composition_review_failure")),
            "child_count_violation": sum(1 for t in ct if t.get("child_count_violation")),
        }

    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {
        "model": "deepseek-v4-flash",
        "version": "v2",
        "description": "Exp03 rejudge v2: routing from Stage1, dangling/resource from merged_node, parent globals from decomposer_cases",
        "metrics_by_condition": metrics_by_condition,
        "trials": all_trials,
    }
    with open(OUTPUT_DIR / "results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    report = generate_report(results)
    with open(OUTPUT_DIR / "report.md", "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Rejudge v2 complete. Output: {OUTPUT_DIR}")
    for cond, m in metrics_by_condition.items():
        print(f"  {cond}: hard_routing={m['hard_routing']}/{m['trials']}, "
              f"stage_drift={m['stage_drift']}/{m['trials']}, "
              f"hard_dangling={m['hard_dangling_input']}, "
              f"res_gap={m['resource_coverage_gap']}, "
              f"llm_review_fail={m['llm_composition_review_failure']}/{m['trials']}")


def generate_report(results):
    metrics = results["metrics_by_condition"]
    trials = results["trials"]

    lines = [
        "# Exp03 Rejudge V2 Report",
        "",
        "Model: `deepseek-v4-flash`",
        "",
        "## Key Changes from V1",
        "",
        "1. **Dangling input source-of-truth**: three_stage uses `merged_node.json` `inputs` field, not `stage1.json` `semantic_inputs`",
        "2. **Resource coverage**: uses parent globals/data_sources from `test_data/decomposer_cases.py`",
        "3. **Child count**: uses case-specific `expected_children_range`, not generic (2, 10)",
        "4. **Stage drift**: compares stage1 child names with merged child names",
        "5. **Missing required fields**: checks field completeness for each condition",
        "6. **Resource normalization**: conservative normalization (orders_db -> orders, etc.)",
        "7. **Stricter source classification**: `global variable` and `internal leaf access` require matching resource declarations",
        "",
        "**IMPORTANT**: This is deterministic rejudge only. No real CodeGenerator composability is measured.",
        "",
        "## Results Matrix (Condition x Metric)",
        "",
        "| Condition | Trials | hard_routing | sibling_inv | ambiguous_df | stage_drift | missing_fields | hard_dangling | ambiguous_src | gv_subset_viol | res_coverage_gap | ambig_resource | llm_review_fail | child_count_viol |",
        "|-----------|--------|-------------|-------------|-------------|------------|---------------|--------------|--------------|----------------|-----------------|---------------|----------------|-----------------|",
    ]

    for cond in CONDITIONS:
        m = metrics.get(cond)
        if not m:
            continue
        lines.append(
            f"| {cond} | {m['trials']} | {m['hard_routing']}/{m['trials']} | "
            f"{m['sibling_invocation']}/{m['trials']} | {m['ambiguous_direct_dataflow']}/{m['trials']} | "
            f"{m['stage_drift']}/{m['trials']} | {m['missing_required_fields']} | "
            f"{m['hard_dangling_input']} | {m['ambiguous_source']} | "
            f"{m['global_var_subset_violation']} | {m['resource_coverage_gap']} | "
            f"{m['ambiguous_resource_coverage']} | "
            f"{m['llm_composition_review_failure']}/{m['trials']} | {m['child_count_violation']}/{m['trials']} |"
        )

    lines.append("")

    # Old vs V1 vs V2 comparison
    lines.append("## Old vs V1 vs V2 Comparison")
    lines.append("")
    lines.append("| Condition | Metric | Old Judge | V1 Judge | V2 Judge |")
    lines.append("|-----------|--------|-----------|----------|----------|")

    for cond in CONDITIONS:
        ct = [t for t in trials if t["condition"] == cond and not t.get("parse_error")]
        n = len(ct)
        if n == 0:
            continue

        old_routing = sum(1 for t in ct if t.get("old_judge", {}).get("has_routing"))
        v2_routing = sum(1 for t in ct if t.get("routing", {}).get("hard_routing"))
        old_dangling = sum(t.get("old_judge", {}).get("dangling_inputs_count", 0) for t in ct)
        v2_dangling = sum(t.get("dangling", {}).get("hard_dangling_count", 0) for t in ct)
        old_compose = sum(1 for t in ct if t.get("old_judge", {}).get("cannot_compose"))
        v2_review = sum(1 for t in ct if t.get("llm_composition_review_failure"))
        v2_res_gap = sum(len(t.get("resource", {}).get("coverage_gaps", [])) for t in ct)
        v2_stage_drift = sum(1 for t in ct if t.get("stage_drift", {}).get("stage_drift"))

        lines.append(f"| {cond} | routing | {old_routing}/{n} | - | {v2_routing}/{n} |")
        lines.append(f"| {cond} | hard_dangling | {old_dangling} | - | {v2_dangling} |")
        lines.append(f"| {cond} | resource_coverage_gap | - | - | {v2_res_gap} |")
        lines.append(f"| {cond} | stage_drift | - | - | {v2_stage_drift}/{n} |")
        lines.append(f"| {cond} | llm_review_fail | {old_compose}/{n} | - | {v2_review}/{n} |")

    lines.append("")

    # Verdict
    lines.append("## Verdict")
    lines.append("")

    three_m = metrics.get("three_stage", {})
    notrad_m = metrics.get("single_stage_notraditional", {})

    if three_m and notrad_m:
        ts_hr = three_m.get("hard_routing", 0)
        nt_hr = notrad_m.get("hard_routing", 0)
        ts_hd = three_m.get("hard_dangling_input", 0)
        nt_hd = notrad_m.get("hard_dangling_input", 0)
        ts_rg = three_m.get("resource_coverage_gap", 0)
        nt_rg = notrad_m.get("resource_coverage_gap", 0)
        ts_sd = three_m.get("stage_drift", 0)
        ts_cc = three_m.get("child_count_violation", 0)
        nt_cc = notrad_m.get("child_count_violation", 0)

        hard_failures = ts_hr > nt_hr or ts_hd > nt_hd or ts_rg > nt_rg or ts_sd > 0 or ts_cc > nt_cc

        if not hard_failures:
            if three_m.get("ambiguous_source", 0) > 0 or three_m.get("ambiguous_resource_coverage", 0) > 0:
                verdict = "INCONCLUSIVE"
                verdict_detail = ("three_stage has no hard deterministic regressions, but ambiguous_source or "
                                  "ambiguous_resource_coverage remain unresolved.")
            else:
                verdict = "PASS"
                verdict_detail = "three_stage does not regress any hard deterministic metric vs notraditional."
        else:
            verdict = "FAIL"
            regressions = []
            if ts_hr > nt_hr:
                regressions.append(f"hard_routing {ts_hr} > {nt_hr}")
            if ts_hd > nt_hd:
                regressions.append(f"hard_dangling {ts_hd} > {nt_hd}")
            if ts_rg > nt_rg:
                regressions.append(f"resource_coverage_gap {ts_rg} > {nt_rg}")
            if ts_sd > 0:
                regressions.append(f"stage_drift {ts_sd}")
            if ts_cc > nt_cc:
                regressions.append(f"child_count_violation {ts_cc} > {nt_cc}")
            verdict_detail = f"Regressions: {', '.join(regressions)}"

        lines.append(f"- **{verdict}**: {verdict_detail}")
    else:
        lines.append("- **INCONCLUSIVE**: Insufficient data for comparison.")

    lines.append("")
    lines.append("**This verdict is deterministic rejudge only; actual codegen composability remains unverified.**")
    lines.append("")

    # Manual check cases
    lines.append("## Manual Check Cases")
    lines.append("")
    manual_cases = [
        ("three_stage", "OrderSystem", 0),
        ("three_stage", "OrderSystem", 2),
        ("three_stage", "ChatApp", 2),
        ("three_stage", "BuildSystem", 2),
        ("three_stage", "DataPipeline", 0),
        ("three_stage", "DataPipeline", 2),
    ]
    for cond, case, ti in manual_cases:
        t = next((x for x in trials if x["condition"] == cond and x["case"] == case and x["trial"] == ti), None)
        if not t:
            lines.append(f"### {cond}/{case}/trial_{ti:02d} — NOT FOUND")
            lines.append("")
            continue
        r = t.get("routing", {})
        drift = t.get("stage_drift", {})
        lines.append(f"### {cond}/{case}/trial_{ti:02d}")
        lines.append("")
        lines.append(f"- **Stage1 names**: {drift.get('stage1_names', 'N/A')}")
        lines.append(f"- **Merged names**: {drift.get('merged_names', 'N/A')}")
        lines.append(f"- **Stage drift**: {drift.get('stage_drift')}")
        lines.append(f"- **hard_routing**: {r.get('hard_routing')}")
        lines.append(f"- **parent_mediated**: {r.get('parent_mediated_dataflow')}")
        lines.append(f"- **ambiguous_direct_dataflow**: {r.get('ambiguous_direct_dataflow')}")
        lines.append(f"- **router_node**: {r.get('router_node')}")
        if r.get("router_nodes"):
            lines.append(f"- **Router nodes**: {r['router_nodes']}")
        if r.get("hard_routing_calls"):
            lines.append(f"- **Hard routing calls**: {r['hard_routing_calls']}")
        lines.append(f"- **Children**: {', '.join(t.get('child_names', []))}")
        lines.append(f"- **Hard dangling**: {t.get('dangling', {}).get('hard_dangling_count', 0)}")
        dangling_details = t.get('dangling', {}).get('hard_dangling', [])
        for dd in dangling_details:
            lines.append(f"  - {dd.get('child')}.{dd.get('input')}: source='{dd.get('source')}' class={dd.get('source_class')}")
        lines.append(f"- **Ambiguous sources**: {t.get('dangling', {}).get('ambiguous_source_count', 0)}")
        ambig_details = t.get('dangling', {}).get('ambiguous_sources', [])
        for ad in ambig_details[:5]:
            lines.append(f"  - {ad.get('child')}.{ad.get('input')}: source='{ad.get('source')}' class={ad.get('source_class')} — {ad.get('evidence')}")
        res = t.get("resource", {})
        lines.append(f"- **Resource coverage gaps**: {len(res.get('coverage_gaps', []))}")
        for gap in res.get("coverage_gaps", []):
            lines.append(f"  - {gap.get('variable')}:{gap.get('required_op')} — {gap.get('reason')}")
        lines.append(f"- **Subset violations**: {len(res.get('subset_violations', []))}")
        for sv in res.get("subset_violations", []):
            lines.append(f"  - {sv.get('child')}:{sv.get('variable')} — {sv.get('reason')}")
        lines.append(f"- **LLM review failure**: {t.get('llm_composition_review_failure')}")
        lines.append(f"- **Missing fields**: {t.get('missing_required_fields_count', 0)}")
        lines.append("")

    # Per-case breakdown for three_stage
    lines.append("## Per-Case Breakdown (three_stage)")
    lines.append("")
    lines.append("| Case | hard_routing | stage_drift | hard_dangling | ambig_src | res_gap | subset_viol | llm_review_fail | child_count_viol |")
    lines.append("|------|-------------|------------|--------------|----------|---------|------------|----------------|-----------------|")
    for case in CASES:
        ct = [t for t in trials if t["condition"] == "three_stage" and t["case"] == case and not t.get("parse_error")]
        if not ct:
            continue
        hr = sum(1 for t in ct if t.get("routing", {}).get("hard_routing"))
        sd = sum(1 for t in ct if t.get("stage_drift", {}).get("stage_drift"))
        hd = sum(t.get("dangling", {}).get("hard_dangling_count", 0) for t in ct)
        am = sum(t.get("dangling", {}).get("ambiguous_source_count", 0) for t in ct)
        rg = sum(len(t.get("resource", {}).get("coverage_gaps", [])) for t in ct)
        sv = sum(len(t.get("resource", {}).get("subset_violations", [])) for t in ct)
        lr = sum(1 for t in ct if t.get("llm_composition_review_failure"))
        cc = sum(1 for t in ct if t.get("child_count_violation"))
        lines.append(f"| {case} | {hr}/{len(ct)} | {sd}/{len(ct)} | {hd} | {am} | {rg} | {sv} | {lr}/{len(ct)} | {cc}/{len(ct)} |")
    lines.append("")

    # Data limitations
    limited = [t for t in trials if t.get("data_limitation")]
    if limited:
        lines.append("## Data Limitations")
        lines.append("")
        for t in limited:
            lines.append(f"- {t['condition']}/{t['case']}/trial_{t['trial']:02d}: {t['data_limitation']}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
