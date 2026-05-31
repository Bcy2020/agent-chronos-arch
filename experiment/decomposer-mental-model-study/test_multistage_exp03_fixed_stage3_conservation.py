"""
Exp03 Fixed-Input Stage3 Conservation Experiment.

Freezes Stage1 and Stage2 from the original Exp03 three_stage run,
reruns only Stage3 with the conservation prompt, and repeats each
frozen input 3 times to measure Stage3 stochasticity.

Output: output/multistage_exp03_fixed_stage3_conservation/{model}/
"""
import json, os, sys, time, re, argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from openai import OpenAI

def _env(key, default=""):
    return os.getenv(key) or os.getenv(f"DEEPSEEK_{key.removeprefix('CHRONOS_')}") or default

TEMPERATURE = float(os.getenv("CHRONOS_TEMPERATURE", "0.3"))
MAX_TOKENS = int(os.getenv("CHRONOS_MAX_TOKENS", "16384"))
MAX_CONCURRENCY = 5

SCRIPT_DIR = Path(__file__).parent
FROZEN_DIR = SCRIPT_DIR / "output" / "multistage_exp03_pipeline_regression" / "deepseek-v4-flash" / "three_stage"
OUTPUT_DIR = SCRIPT_DIR / "output" / "multistage_exp03_fixed_stage3_conservation"

# Import decomposer_cases for parent case definitions
sys.path.insert(0, str(SCRIPT_DIR / "test_data"))
from decomposer_cases import ALL_CASES

CASE_BY_NAME = {}
for case in ALL_CASES:
    CASE_BY_NAME[case["node"].name] = case

CASES = ["OrderSystem", "ChatApp", "PatientPortal", "BuildSystem", "DataPipeline"]
DEFAULT_REPEATS = 3

# ========================================================================
# Stage 3 conservation prompt (identical to test_multistage_exp03_pipeline_regression.py)
# ========================================================================

STAGE3_SYSTEM_PROMPT = """You are a governance and resource derivation agent. Given frozen Stage 1 + Stage 2, derive resource allocation and governance fields.

RULES:
1. Do NOT change Stage 1 semantics or Stage 2 signatures.
2. Do NOT add, delete, rename, or reorder children.
3. Derive ONLY: global_vars, data_operations, requested_capabilities, constraints, acceptance_criteria, traceability, node_type.
4. Each child's global_vars MUST be a subset of the parent's global_vars.

GLOBAL STATE CONSERVATION — HARD REQUIREMENT:
The parent's global_vars are an architectural contract. You MUST distribute them to children.
For every parent global var, the union of all child global_vars MUST cover the parent's required operation.
If parent requires read_write on X, children must collectively cover both read and write on X.
It is valid to assign read and write to different children, but neither side may disappear.
Do not only infer local child needs; first satisfy the parent conservation ledger, then assign operations to responsible children.
A child global_vars variable must come from parent global_vars — do not invent new variables.
data_operations should be consistent with global_vars.
requested_capabilities should reflect the same resource operation needs.
Do not silently drop any parent operation.

SELF-CHECK before returning JSON:
- List every parent global var and its required op.
- For each, confirm which child (or children) covers it.
- If any parent op is unassigned, fix it before responding.

OUTPUT FORMAT — Return valid JSON:
{
  "children": [
    {
      "name": "ChildName (UNCHANGED)",
      "purpose": "(UNCHANGED from Stage 1)",
      "behavior": "(UNCHANGED from Stage 1)",
      "inputs": ["(UNCHANGED from Stage 2)"],
      "outputs": ["(UNCHANGED from Stage 2)"],
      "signature": "(UNCHANGED from Stage 2)",
      "global_vars": [{"variable": "var_name", "op": "read|write|read_write", "description": ""}],
      "data_operations": [{"source_name": "source", "operation_type": "read|write|read_write", "description": ""}],
      "requested_capabilities": ["resource.operation"],
      "constraints": [{"constraint_id": "C-001", "description": ""}],
      "acceptance_criteria": [{"ac_id": "AC-001", "description": ""}],
      "traceability": {"parent_requirement_ids": ["FR-001"]},
      "node_type": "pure_function|atomic_operation",
      "stop_decompose": false,
      "stop_reason": ""
    }
  ],
  "governance_notes": ""
}"""


def build_stage3_user_prompt(stage1_data, stage2_data, node):
    children = stage2_data.get("children", stage1_data.get("children", []))
    lines = [
        "Derive governance and resource fields for each child.", "",
        f"Parent: {node.name}",
        f"Purpose: {node.purpose}", "",
    ]
    if node.data_sources:
        lines.append("Available Data Stores:")
        for ds in node.data_sources:
            lines.append(f"  - {ds.name} ({ds.category}, {ds.access})")
        lines.append("")
    if node.global_vars:
        lines.append("=== PARENT GLOBAL STATE CONSERVATION LEDGER ===")
        lines.append("Every row below MUST be covered by the union of child global_vars.")
        lines.append("Do not drop any row. If a row requires read_write, both read and write must appear.")
        lines.append("")
        lines.append("| Variable | Required Op | Description |")
        lines.append("|----------|-------------|-------------|")
        for gv in node.global_vars:
            lines.append(f"| {gv.variable} | {gv.op} | {gv.description} |")
        lines.append("")
        lines.append("After assigning child global_vars, verify every row above is covered.")
        lines.append("")
    lines.append("Children (frozen from Stage 1 + Stage 2):")
    for c in children:
        lines.append(f"  {c.get('name', '')}: {c.get('purpose', '')}")
        sig = c.get("signature", "")
        if sig:
            lines.append(f"    signature: {sig}")
    lines.append("")
    lines.append("Return ONLY the JSON response.")
    return "\n".join(lines)


# ========================================================================
# Utilities
# ========================================================================

class LLMLogger:
    def __init__(self, log_dir, api_key, base_url, model):
        self.log_dir = log_dir; self.api_key = api_key; self.base_url = base_url; self.model = model
        self.call_counter = 0
        os.makedirs(log_dir, exist_ok=True)

    def chat(self, messages, max_tokens=None):
        self.call_counter += 1; call_id = self.call_counter
        max_tokens = max_tokens or MAX_TOKENS
        req = {"call_id": call_id, "timestamp": time.time(), "messages": messages, "max_tokens": max_tokens, "model": self.model}
        with open(os.path.join(self.log_dir, f"{call_id:04d}_request.json"), "w", encoding="utf-8") as f:
            json.dump(req, f, indent=2, ensure_ascii=False)
        client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=120)
        start = time.time()
        try:
            resp = client.chat.completions.create(**dict(model=self.model, messages=messages, temperature=TEMPERATURE, max_tokens=max_tokens, extra_body={"thinking": {"type": "disabled"}}))
            text = resp.choices[0].message.content
        except Exception as e:
            with open(os.path.join(self.log_dir, f"{call_id:04d}_response.json"), "w", encoding="utf-8") as f:
                json.dump({"call_id": call_id, "elapsed": round(time.time()-start, 2), "error": str(e)}, f, indent=2)
            raise
        elapsed = time.time() - start
        with open(os.path.join(self.log_dir, f"{call_id:04d}_response.json"), "w", encoding="utf-8") as f:
            json.dump({"call_id": call_id, "elapsed": round(elapsed, 2), "response": text}, f, indent=2)
        return text


def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    if "}" in text:
        text = text[:text.rfind("}")+1]
    text = re.sub(r'(?<=[\s:,\[{])[fFrRuUbB]+(")', r'\1', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except:
                pass
    return {"error": "JSON parse failed", "raw": text[:500]}


def load_json_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def merge_stages(stage1, stage2, stage3):
    """Merge three stages into a single children list."""
    s1_children = {c.get("name", ""): c for c in stage1.get("children", [])}
    s2_children = {c.get("name", ""): c for c in stage2.get("children", [])}
    s3_children = {c.get("name", ""): c for c in stage3.get("children", [])}

    merged = []
    for name in s1_children:
        m = {}
        m.update(s1_children[name])
        if name in s2_children:
            s2 = s2_children[name]
            for key in ("inputs", "outputs", "signature"):
                if key in s2:
                    m[key] = s2[key]
        if name in s3_children:
            s3 = s3_children[name]
            for key in ("global_vars", "data_operations", "requested_capabilities",
                        "constraints", "acceptance_criteria", "traceability", "node_type"):
                if key in s3:
                    m[key] = s3[key]
        merged.append(m)
    return merged


def check_stage3_preservation(stage1, stage2, stage3, merged):
    """Check that Stage 3 did not add, delete, rename, or reorder children,
    and did not change Stage 2 interfaces."""
    s1_names = [c.get("name", "") for c in stage1.get("children", [])]
    s2_names = [c.get("name", "") for c in stage2.get("children", [])]
    s3_names = [c.get("name", "") for c in stage3.get("children", [])]
    merged_names = [c.get("name", "") for c in merged]

    drift_issues = []

    # Child identity preservation
    if s3_names != s1_names:
        drift_issues.append(f"child_names_changed: s1={s1_names} s3={s3_names}")
    if merged_names != s1_names:
        drift_issues.append(f"merged_names_differ: s1={s1_names} merged={merged_names}")

    # Interface preservation (inputs, outputs, signature from Stage 2)
    s2_map = {c.get("name", ""): c for c in stage2.get("children", [])}
    for c in merged:
        cname = c.get("name", "")
        if cname not in s2_map:
            continue
        s2c = s2_map[cname]
        for field in ("inputs", "outputs", "signature"):
            s2_val = s2c.get(field)
            merged_val = c.get(field)
            if s2_val is not None and merged_val != s2_val:
                drift_issues.append(f"{cname}.{field}: Stage2 != merged")

    return {
        "stage3_interface_drift": len(drift_issues) > 0,
        "drift_issues": drift_issues,
        "s1_names": s1_names,
        "s2_names": s2_names,
        "s3_names": s3_names,
        "merged_names": merged_names,
    }


# ========================================================================
# Resource coverage and deterministic checks (inline, same as rejudge)
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


def check_resource_coverage(merged_children, parent_node):
    """Check resource coverage gaps (same logic as rejudge)."""
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

    child_union = {}
    for c in merged_children:
        for gv in c.get("global_vars", []):
            var = gv.get("variable", gv.get("var", ""))
            op = normalize_op(gv.get("op", gv.get("operation_type", "read")))
            nvar = normalize_resource_name(var)
            child_union.setdefault(nvar, set()).add(op)
        for do in c.get("data_operations", []):
            src = do.get("source_name", "")
            op = normalize_op(do.get("operation_type", "read"))
            if src:
                nsrc = normalize_resource_name(src)
                child_union.setdefault(nsrc, set()).add(op)

    gaps = []
    for var, required_ops in parent_resources.items():
        child_ops = child_union.get(var, set())
        for req_op in required_ops:
            covered = False
            if req_op == "read_write":
                covered = "read_write" in child_ops or ("read" in child_ops and "write" in child_ops)
            elif req_op == "read":
                covered = "read" in child_ops or "read_write" in child_ops
            elif req_op == "write":
                covered = "write" in child_ops or "read_write" in child_ops
            if not covered:
                gaps.append({"variable": var, "required_op": req_op, "child_ops": sorted(child_ops),
                             "reason": f"No child covers {var}:{req_op}"})
    return gaps, {k: sorted(v) for k, v in child_union.items()}


def check_governance_notes_self_check(governance_notes, coverage_gaps):
    """Check if governance_notes claims coverage but deterministic judge found gaps.
    Returns count of false self-checks."""
    if not governance_notes or not isinstance(governance_notes, str):
        return 0
    notes_lower = governance_notes.lower()
    false_count = 0
    # If there are coverage gaps but governance_notes claims "all covered" or "verified"
    if coverage_gaps:
        claim_phrases = ["all covered", "all rows covered", "every row covered",
                         "conservation satisfied", "all global vars covered",
                         "all parent global", "verified", "no gaps", "complete coverage"]
        for phrase in claim_phrases:
            if phrase in notes_lower:
                false_count = len(coverage_gaps)  # all gaps are false self-checks
                break
    return false_count


def check_missing_fields(children):
    required = ["name", "purpose", "behavior", "inputs", "outputs", "signature",
                "global_vars", "data_operations", "constraints", "acceptance_criteria",
                "traceability", "node_type"]
    missing = []
    for c in children:
        cname = c.get("name", "?")
        for f in required:
            if f not in c or c[f] is None:
                missing.append(f"{cname}:{f}")
    return missing


def check_global_var_subset(children, parent_globals):
    parent_vars = {(g.variable if hasattr(g, 'variable') else g.get("variable", "")) for g in parent_globals}
    violations = []
    for c in children:
        cname = c.get("name", "")
        for gv in c.get("global_vars", []):
            var = gv.get("variable", "") if isinstance(gv, dict) else gv.variable
            if var and var not in parent_vars:
                violations.append(f"{cname}:{var}")
    return violations


# ========================================================================
# Trial runner
# ========================================================================

def _fix_constraints(node):
    """Convert string constraints to dict format."""
    import copy
    node = copy.deepcopy(node)
    if node.subprd and node.subprd.constraints:
        fixed = []
        for c in node.subprd.constraints:
            if isinstance(c, str):
                fixed.append({"description": c})
            elif isinstance(c, dict):
                fixed.append(c)
            else:
                fixed.append({"description": str(c)})
        node.subprd.constraints = fixed
    return node


def run_repeat(case_name, trial_idx, repeat_idx, stage1_data, stage2_data, parent_case, api_key, base_url, model):
    """Run a single Stage3 repeat on frozen Stage1+Stage2 inputs."""
    node = _fix_constraints(parent_case["node"])
    label = f"three_stage/{case_name}/trial_{trial_idx:02d}/repeat_{repeat_idx:02d}"
    log_dir = os.path.join(OUTPUT_DIR, model, "three_stage", case_name, f"trial_{trial_idx:02d}", f"repeat_{repeat_idx:02d}")
    logger = LLMLogger(log_dir, api_key, base_url, model)
    t0 = time.time()

    # Save frozen inputs for auditability
    with open(os.path.join(log_dir, "stage1.json"), "w", encoding="utf-8") as f:
        json.dump(stage1_data, f, indent=2, ensure_ascii=False)
    with open(os.path.join(log_dir, "stage2.json"), "w", encoding="utf-8") as f:
        json.dump(stage2_data, f, indent=2, ensure_ascii=False)

    # Stage 3 call
    try:
        s3_raw = logger.chat([
            {"role": "system", "content": STAGE3_SYSTEM_PROMPT},
            {"role": "assistant", "content": json.dumps(stage2_data, indent=2, ensure_ascii=False)},
            {"role": "user", "content": build_stage3_user_prompt(stage1_data, stage2_data, node)},
        ])
    except Exception as e:
        return {"label": label, "case": case_name, "trial": trial_idx, "repeat": repeat_idx,
                "error": f"Stage3 API failed: {e}", "elapsed": time.time()-t0, "llm_calls": 1}

    stage3 = parse_json(s3_raw)
    elapsed = round(time.time()-t0, 1)

    if "error" in stage3 and not stage3.get("children"):
        return {"label": label, "case": case_name, "trial": trial_idx, "repeat": repeat_idx,
                "error": f"Stage3 parse: {stage3.get('error')}", "elapsed": elapsed, "llm_calls": 1,
                "parse_error": True}

    with open(os.path.join(log_dir, "stage3.json"), "w", encoding="utf-8") as f:
        json.dump(stage3, f, indent=2, ensure_ascii=False)

    # Merge
    merged = merge_stages(stage1_data, stage2_data, stage3)
    with open(os.path.join(log_dir, "merged_node.json"), "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    # Checks
    preservation = check_stage3_preservation(stage1_data, stage2_data, stage3, merged)
    coverage_gaps, child_union = check_resource_coverage(merged, node)
    missing_fields = check_missing_fields(merged)
    gv_subset = check_global_var_subset(merged, node.global_vars)
    governance_notes = stage3.get("governance_notes", "")
    false_self_check = check_governance_notes_self_check(governance_notes, coverage_gaps)

    result = {
        "label": label, "condition": "three_stage", "case": case_name,
        "trial": trial_idx, "repeat": repeat_idx,
        "n_children": len(merged),
        "child_names": [c.get("name", "") for c in merged],
        "stage3_interface_drift": preservation["stage3_interface_drift"],
        "drift_issues": preservation["drift_issues"],
        "resource_coverage_gaps": coverage_gaps,
        "resource_coverage_gap_count": len(coverage_gaps),
        "child_resource_union": child_union,
        "missing_required_fields": missing_fields[:20],
        "missing_required_fields_count": len(missing_fields),
        "global_var_subset_violations": gv_subset[:20],
        "governance_notes": governance_notes[:500],
        "false_self_check_count": false_self_check,
        "parse_error": False,
        "elapsed": elapsed, "llm_calls": logger.call_counter,
    }

    with open(os.path.join(log_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    return result


# ========================================================================
# Report generation
# ========================================================================

def generate_report(all_results, model, n_repeats):
    lines = [
        "# Exp03 Fixed-Input Stage3 Conservation Report",
        "",
        f"Model: `{model}`",
        f"Cases: {', '.join(CASES)}",
        f"Repeats per frozen input: {n_repeats}",
        "",
        "## Design",
        "",
        "This experiment freezes Stage1 and Stage2 from the original Exp03 three_stage run",
        "and reruns only Stage3 with the conservation prompt. This isolates Stage3 resource",
        "allocation quality from Stage1/2 sampling noise.",
        "",
    ]

    # Aggregate metrics
    n_total = len(all_results)
    n_parse_errors = sum(1 for r in all_results if r.get("parse_error") or r.get("error"))
    n_drift = sum(1 for r in all_results if r.get("stage3_interface_drift"))
    total_gaps = sum(r.get("resource_coverage_gap_count", 0) for r in all_results)
    total_false_self_check = sum(r.get("false_self_check_count", 0) for r in all_results)
    n_missing_fields = sum(r.get("missing_required_fields_count", 0) for r in all_results)
    n_subset_viol = sum(len(r.get("global_var_subset_violations", [])) for r in all_results)

    lines.append("## Aggregate Metrics\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total repeats | {n_total} |")
    lines.append(f"| Parse errors | {n_parse_errors} |")
    lines.append(f"| Stage3 interface drift | {n_drift} |")
    lines.append(f"| Resource coverage gaps (total) | {total_gaps} |")
    lines.append(f"| False self-check (claims covered, judge disagrees) | {total_false_self_check} |")
    lines.append(f"| Missing required fields | {n_missing_fields} |")
    lines.append(f"| Global var subset violations | {n_subset_viol} |")
    lines.append("")

    # Per-case breakdown
    lines.append("## Per-Case Breakdown\n")
    lines.append("| Case | Repeats | Parse Err | Drift | Res Gaps | False Self-Check | Missing Fields |")
    lines.append("|------|---------|-----------|-------|----------|-----------------|----------------|")
    for case_name in CASES:
        ct = [r for r in all_results if r.get("case") == case_name]
        if not ct: continue
        n = len(ct)
        pe = sum(1 for r in ct if r.get("parse_error") or r.get("error"))
        dr = sum(1 for r in ct if r.get("stage3_interface_drift"))
        rg = sum(r.get("resource_coverage_gap_count", 0) for r in ct)
        fs = sum(r.get("false_self_check_count", 0) for r in ct)
        mf = sum(r.get("missing_required_fields_count", 0) for r in ct)
        lines.append(f"| {case_name} | {n} | {pe} | {dr} | {rg} | {fs} | {mf} |")
    lines.append("")

    # Per-variable gap distribution
    lines.append("## Per-Variable Gap Distribution\n")
    gap_counter = {}
    for r in all_results:
        for gap in r.get("resource_coverage_gaps", []):
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

    # Comparison with v2 baseline
    v2_results_path = SCRIPT_DIR / "output" / "multistage_exp03_pipeline_regression_rejudged_v2" / "deepseek-v4-flash" / "results.json"
    if v2_results_path.exists():
        with open(v2_results_path, "r", encoding="utf-8") as f:
            v2_data = json.load(f)
        v2_metrics = v2_data.get("metrics_by_condition", {})
        v2_three = v2_metrics.get("three_stage", {})
        v2_res_gap = v2_three.get("resource_coverage_gap", "N/A")
        v2_hard_routing = v2_three.get("hard_routing", "N/A")
        v2_stage_drift = v2_three.get("stage_drift", "N/A")

        lines.append("## Comparison with V2 Baseline (three_stage)\n")
        lines.append("| Metric | V2 Baseline | Fixed-Input Conservation | Delta |")
        lines.append("|--------|-------------|-------------------------|-------|")
        lines.append(f"| resource_coverage_gap | {v2_res_gap} | {total_gaps} | {total_gaps - v2_res_gap if isinstance(v2_res_gap, int) else 'N/A'} |")
        lines.append(f"| hard_routing (frozen context) | {v2_hard_routing} | N/A (frozen) | — |")
        lines.append(f"| stage_drift | {v2_stage_drift} | {n_drift} | {n_drift - v2_stage_drift if isinstance(v2_stage_drift, int) else 'N/A'} |")
        lines.append("")

    # Verdict
    lines.append("## Verdict\n")
    if n_parse_errors > 0:
        lines.append(f"- **FAIL**: {n_parse_errors} parse errors")
    elif n_drift > 0:
        lines.append(f"- **FAIL**: {n_drift} stage3 interface drift occurrences")
    elif total_gaps > 0:
        lines.append(f"- **FAIL**: {total_gaps} resource coverage gaps remain across {n_total} repeats")
    else:
        lines.append(f"- **PASS**: zero parse errors, zero drift, zero resource coverage gaps across {n_total} repeats")
    lines.append("")
    lines.append("## Preliminary Analysis\n")
    if total_gaps > 0 and n_drift == 0 and n_parse_errors == 0:
        lines.append("Stage3 conservation prompt does not eliminate resource coverage gaps even with")
        lines.append("frozen Stage1/Stage2 inputs. The gaps are Stage3-specific, not caused by")
        lines.append("upstream sampling noise.")
    elif total_gaps == 0 and n_drift == 0 and n_parse_errors == 0:
        lines.append("Stage3 conservation prompt successfully eliminates resource coverage gaps")
        lines.append("when Stage1/Stage2 are frozen. The previous regression was attributable to")
        lines.append("upstream sampling noise.")
    lines.append("")

    # Manual sampling notes
    lines.append("## Manual Sampling Notes\n")
    drift_cases = [r for r in all_results if r.get("stage3_interface_drift")]
    if drift_cases:
        lines.append("### Stage3 Interface Drift Cases\n")
        for r in drift_cases[:5]:
            lines.append(f"- **{r['label']}**: {r.get('drift_issues', [])}")
        lines.append("")

    gap_cases = [r for r in all_results if r.get("resource_coverage_gap_count", 0) > 0]
    if gap_cases:
        lines.append("### Resource Gap Cases (sampled)\n")
        # Show one per case
        seen_cases = set()
        for r in gap_cases:
            if r["case"] in seen_cases:
                continue
            seen_cases.add(r["case"])
            lines.append(f"#### {r['label']}\n")
            lines.append(f"- Child names: {r.get('child_names', [])}")
            lines.append(f"- Child resource union: {r.get('child_resource_union', {})}")
            lines.append(f"- Gaps:")
            for gap in r.get("resource_coverage_gaps", []):
                lines.append(f"  - {gap['variable']}:{gap['required_op']} — {gap['reason']} (child ops: {gap['child_ops']})")
            gn = r.get("governance_notes", "")
            if gn:
                lines.append(f"- Governance notes (excerpt): {gn[:200]}")
            lines.append("")

    return "\n".join(lines)


# ========================================================================
# Main
# ========================================================================

def main():
    parser = argparse.ArgumentParser(description="Exp03 Fixed-Input Stage3 Conservation")
    parser.add_argument("--model", type=str, default="deepseek-v4-flash")
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--cases", type=str, default=",".join(CASES))
    parser.add_argument("--base_url", type=str, default=None)
    parser.add_argument("--api_key", type=str, default=None)
    args = parser.parse_args()

    model = args.model
    if model in {"mimo-v2.5", "mimo-v2-flash", "mimo-v2.5-pro", "mimo-v2-pro", "mimo-v2-omni"}:
        base_url = args.base_url or os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
        api_key = args.api_key or os.getenv("MIMO_API_KEY") or _env("CHRONOS_API_KEY")
    else:
        base_url = args.base_url or _env("CHRONOS_BASE_URL", "https://api.deepseek.com")
        api_key = args.api_key or _env("CHRONOS_API_KEY")

    if not api_key:
        print("ERROR: Set CHRONOS_API_KEY"); return 1

    requested_cases = [c.strip() for c in args.cases.split(",")]
    print(f"Model: {model}")
    print(f"Cases: {requested_cases}")
    print(f"Repeats per frozen input: {args.repeats}")
    print(f"Frozen input: {FROZEN_DIR}")
    print(f"Output: {OUTPUT_DIR}/{model}/")
    print()

    # Build task list: for each case/trial, load frozen stage1+stage2, then repeat Stage3
    tasks = []
    for case_name in requested_cases:
        case_dir = FROZEN_DIR / case_name
        if not case_dir.exists():
            print(f"  WARNING: No frozen data for {case_name}, skipping")
            continue
        parent_case = CASE_BY_NAME.get(case_name)
        if not parent_case:
            print(f"  WARNING: No parent case for {case_name}, skipping")
            continue
        for trial_dir in sorted(case_dir.iterdir()):
            if not trial_dir.is_dir() or not trial_dir.name.startswith("trial_"):
                continue
            trial_idx = int(trial_dir.name.split("_")[1])
            stage1_file = trial_dir / "stage1.json"
            stage2_file = trial_dir / "stage2.json"
            if not stage1_file.exists() or not stage2_file.exists():
                print(f"  WARNING: Missing frozen files in {trial_dir}, skipping")
                continue
            stage1_data = load_json_file(stage1_file)
            stage2_data = load_json_file(stage2_file)
            for repeat_idx in range(args.repeats):
                tasks.append((case_name, trial_idx, repeat_idx, stage1_data, stage2_data, parent_case))

    print(f"Total tasks: {len(tasks)} ({len(tasks) // max(args.repeats, 1)} frozen inputs x {args.repeats} repeats)")
    print()

    all_results = []
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        futures = {}
        for case_name, trial_idx, repeat_idx, s1, s2, pc in tasks:
            f = pool.submit(run_repeat, case_name, trial_idx, repeat_idx, s1, s2, pc, api_key, base_url, model)
            futures[f] = f"{case_name}/trial_{trial_idx:02d}/repeat_{repeat_idx:02d}"

        for f in as_completed(futures):
            r = f.result()
            all_results.append(r)
            err = r.get("error", "")
            if err:
                print(f"  [{r['label']}] ERROR: {err[:80]}")
            else:
                drift = "DRIFT!" if r.get("stage3_interface_drift") else ""
                gaps = f"gaps={r.get('resource_coverage_gap_count', 0)}"
                print(f"  [{r['label']}] {r.get('n_children',0)}ch {drift} {gaps} {r.get('elapsed',0)}s")

    all_results.sort(key=lambda r: (r.get("case", ""), r.get("trial", 0), r.get("repeat", 0)))

    out_dir = OUTPUT_DIR / model
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSaved: {results_path}")

    report = generate_report(all_results, model, args.repeats)
    report_path = out_dir / "report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Saved: {report_path}")

    # Summary
    total = len(all_results)
    total_err = sum(1 for r in all_results if r.get("error") or r.get("parse_error", False))
    total_drift = sum(1 for r in all_results if r.get("stage3_interface_drift"))
    total_gaps = sum(r.get("resource_coverage_gap_count", 0) for r in all_results)
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Total repeats: {total}")
    print(f"  Errors: {total_err}/{total}")
    print(f"  Stage3 interface drift: {total_drift}/{total}")
    print(f"  Resource coverage gaps: {total_gaps}")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
