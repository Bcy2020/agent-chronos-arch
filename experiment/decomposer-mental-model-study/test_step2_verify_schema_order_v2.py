"""
Step2 Verifier Schema-Order Control Experiment.

Tests whether reordering the verify JSON schema from
  status -> checks -> decomposition_feedback
to
  checks -> decomposition_feedback -> final_status
reduces self-contradictory outputs (status="ok" but failed_checks non-empty).

Verifier-only: reads generated/fake code from clean_v2 artifacts, does NOT
re-run codegen. Compares old_order vs new_order on the same inputs.

Stop rule: run once, report, STOP. No prompt tuning. No MVP modification.
"""
import argparse
import json
import os
import re
import sys
import time as _time
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from config import Config
from api_client import APIClient
from models import (
    Node, InputParam, OutputParam, DataflowEdge, ChildContract,
    SubPRD, AcceptanceCriterion, Traceability, DataOperation,
    Boundary, GlobalVar, DataSource,
)
from code_generator_literal_policy import (
    LiteralPolicyCodeGenerator,
    LITERAL_POLICY_CHECK,
)

MODEL_NAME = "deepseek-chat"
CLEAN_V2_DIR = os.path.join(
    os.path.dirname(__file__),
    "output", "codegen_literal_policy_step2_clean_v2", MODEL_NAME
)
OUTPUT_BASE = os.path.join(
    os.path.dirname(__file__),
    "output", "codegen_step2_verify_schema_order_v2", MODEL_NAME
)


# ============================================================================
# Helpers
# ============================================================================

class _Tee:
    def __init__(self, *streams):
        self._streams = streams

    def write(self, data):
        for stream in self._streams:
            stream.write(data)
            stream.flush()
        return len(data)

    def flush(self):
        for stream in self._streams:
            stream.flush()

    def isatty(self):
        return any(getattr(stream, "isatty", lambda: False)() for stream in self._streams)


def _install_run_log(output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, "run.log")
    log_file = open(log_path, "a", encoding="utf-8", buffering=1)
    log_file.write("\n" + "=" * 80 + "\n")
    log_file.write(f"run_start={_time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
    log_file.flush()
    sys.stdout = _Tee(sys.__stdout__, log_file)
    sys.stderr = _Tee(sys.__stderr__, log_file)
    return log_path


def _save_json(path: str, data: Any):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _save_text(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _call_llm_with_retry(api_client: APIClient, messages: List[Dict],
                          max_tokens: int = 1024, max_attempts: int = 5):
    for attempt in range(max_attempts):
        try:
            response = api_client.chat(messages, max_tokens=max_tokens)
            if response and response.strip():
                return response
            print(f"    (empty response, attempt {attempt+1}/{max_attempts})")
        except Exception as e:
            print(f"    (error: {e}, attempt {attempt+1}/{max_attempts})")
        if attempt < max_attempts - 1:
            _time.sleep(5 * (attempt + 1))
    return ""


def _parse_json_response(response: str) -> Dict[str, Any]:
    """Extract JSON from LLM response, handling markdown fences."""
    if not response:
        return {"error": "Empty response"}
    text = response.strip()
    # Strip markdown code fences
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    # Try to find JSON object
    start = text.find("{")
    if start == -1:
        return {"error": "No JSON object found", "raw": response[:500]}
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i+1])
                except json.JSONDecodeError as e:
                    return {"error": f"JSON parse error: {e}", "raw": text[start:i+1]}
    return {"error": "Unterminated JSON", "raw": text[start:start+500]}


# ============================================================================
# Case definitions — read from clean_v2 artifacts
# ============================================================================

# Mapping: case_id -> (clean_v2 directory name, expected, mode, expected_primary_reason)
CASE_DEFS = {
    "P1": ("case_P1_unsupported_command_branch_literal", "accept", "full_generate", ""),
    "P2": ("case_P2_empty_list_prd_literal", "accept", "full_generate", ""),
    "P3": ("case_P3_conditional_dispatch_no_literals", "accept", "full_generate", ""),
    "N1": ("case_N1_hardcoded_runtime_id", "reject", "verifier_only", "return_value_origin"),
    "N2a": ("case_N2a_literal_substitutes_child_output", "reject", "verifier_only", "return_value_origin"),
    "N2b": ("case_N2b_full_generate_child_output_required", "accept", "full_generate", ""),
    "N3a": ("case_N3a_runtime_status_hardcoded", "reject", "verifier_only", "return_value_origin"),
    "N3b": ("case_N3b_full_generate_status_child_required", "accept", "full_generate", ""),
    "N4": ("case_N4_missing_capability_masked_by_literal", "reject", "verifier_only", "missing_child_capability"),
    "N5": ("case_N5_sibling_call_violation", "reject", "full_generate", "tree_structure_violation"),
}


def load_clean_v2_case(case_id: str) -> Dict[str, Any]:
    """Load artifacts from clean_v2 output for a given case."""
    dir_name, expected, mode, expected_reason = CASE_DEFS[case_id]
    case_dir = os.path.join(CLEAN_V2_DIR, dir_name)

    result = {
        "case_id": case_id,
        "dir_name": dir_name,
        "expected": expected,
        "mode": mode,
        "expected_reason": expected_reason,
    }

    # Load node
    node_path = os.path.join(case_dir, "node.json")
    if os.path.exists(node_path):
        with open(node_path, "r", encoding="utf-8") as f:
            result["node_json"] = json.load(f)

    # Load generated code (try generated_code.py first, then generated_candidate.py)
    for fname in ("generated_code.py", "generated_candidate.py"):
        code_path = os.path.join(case_dir, fname)
        if os.path.exists(code_path):
            with open(code_path, "r", encoding="utf-8") as f:
                result["code"] = f.read()
            result["code_source"] = fname
            break

    # Load clean_v2 verdict for reference
    verdict_path = os.path.join(case_dir, "verdict.json")
    if os.path.exists(verdict_path):
        with open(verdict_path, "r", encoding="utf-8") as f:
            result["clean_v2_verdict"] = json.load(f)

    # Load literal expectations
    lit_path = os.path.join(case_dir, "literal_policy_expectation.json")
    if os.path.exists(lit_path):
        with open(lit_path, "r", encoding="utf-8") as f:
            result["literal_expectations"] = json.load(f)

    return result


# ============================================================================
# Verify prompt builders
# ============================================================================

# Old order: status -> checks -> decomposition_feedback (current schema)
OLD_ORDER_SCHEMA = '''Return ONLY valid JSON with this structure:
{
  "status": "ok | cannot_compose",
  "checks": {
    "return_value_origin": {"passed": true, "detail": "explanation of the verdict"},
    "child_coverage": {"passed": true, "detail": "explanation of the verdict"},
    "no_direct_access": {"passed": true, "detail": "explanation of the verdict"},
    "no_cross_calls": {"passed": true, "detail": "explanation of the verdict"},
    "dataflow_conformance": {"passed": true, "detail": "explanation of the verdict"}
  },
  "decomposition_feedback": {
    "reason": "missing_child_input_source | missing_child_capability | invalid_child_boundary | wrong_child_signature | cannot_satisfy_parent_output | dataflow_conformance_failure | tree_structure_violation | other",
    "offending_child": "ChildName or empty",
    "failed_checks": ["return_value_origin", "child_coverage"],
    "missing_inputs": [],
    "direct_resource_accesses": [],
    "suggested_fix": "Concrete suggestion for re-decomposition",
    "requires_redecomposition": true
  }
}'''

# New order: checks(detail first) -> decomposition_feedback -> final_status
NEW_ORDER_SCHEMA = '''IMPORTANT: You must complete ALL checks BEFORE deciding final_status.
Within each check, write the detail analysis FIRST, then decide passed based on your analysis.

Return ONLY valid JSON with this structure:
{
  "checks": {
    "return_value_origin": {"detail": "explanation of the verdict", "passed": true},
    "child_coverage": {"detail": "explanation of the verdict", "passed": true},
    "no_direct_access": {"detail": "explanation of the verdict", "passed": true},
    "no_cross_calls": {"detail": "explanation of the verdict", "passed": true},
    "dataflow_conformance": {"detail": "explanation of the verdict", "passed": true}
  },
  "decomposition_feedback": {
    "reason": "missing_child_input_source | missing_child_capability | invalid_child_boundary | wrong_child_signature | cannot_satisfy_parent_output | dataflow_conformance_failure | tree_structure_violation | other",
    "offending_child": "ChildName or empty",
    "failed_checks": ["return_value_origin", "child_coverage"],
    "missing_inputs": [],
    "direct_resource_accesses": [],
    "suggested_fix": "Concrete suggestion for re-decomposition",
    "requires_redecomposition": true
  },
  "final_status": "ok | cannot_compose"
}

CONSTRAINTS ON final_status:
- Do NOT decide final_status until after all checks are completed above.
- If ANY check has passed=false, final_status MUST be "cannot_compose".
- If decomposition_feedback.failed_checks is non-empty, final_status MUST be "cannot_compose".
- If requires_redecomposition=true, final_status MUST be "cannot_compose".
- final_status may be "ok" ONLY when ALL checks passed, failed_checks is empty, and requires_redecomposition=false.

CONSTRAINTS ON each check:
- Write detail FIRST, then decide passed based on your analysis.
- If your detail describes a violation or failure, passed MUST be false.
- passed may be true ONLY when your detail shows no violation.'''


def build_verify_prompt_common(node_dict: Dict, code: str,
                                literal_expectations: Optional[Dict] = None) -> str:
    """Build the common part of the verify user prompt (before schema)."""
    lines = [
        "Review the submitted code below. This code was written by another developer.",
        "",
        "=" * 60,
        "SUBMITTED PARENT FUNCTION",
        "=" * 60,
        f"Name: {node_dict.get('name', '')}",
        f"Purpose: {node_dict.get('purpose', '')}",
        "",
    ]

    # SubPRD context
    subprd = node_dict.get("subprd")
    if subprd:
        lines.append("=" * 60)
        lines.append("PARENT SUBPRD — TASK DEFINITION")
        lines.append("=" * 60)
        if subprd.get("purpose"):
            lines.append(f"Purpose: {subprd['purpose']}")
        if subprd.get("description"):
            lines.append(f"Description: {subprd['description']}")
        if subprd.get("constraints"):
            lines.append("Constraints:")
            for c in subprd["constraints"]:
                if isinstance(c, dict):
                    for k, v in c.items():
                        lines.append(f"  - {k}: {v}")
                else:
                    lines.append(f"  - {c}")
        if subprd.get("acceptance_criteria"):
            lines.append("Acceptance Criteria:")
            for ac in subprd["acceptance_criteria"]:
                ac_id = ac.get("ac_id", "")
                desc = ac.get("description", "")
                lines.append(f"  - [{ac_id}] {desc}")
        lines.append("")

    # Literal expectations
    if literal_expectations:
        lines.append("=" * 60)
        lines.append("DECLARED LITERAL EXPECTATIONS FOR THIS CASE")
        lines.append("=" * 60)
        allowed_list = literal_expectations.get("allowed", [])
        if allowed_list:
            lines.append("Allowed literals (authorized by PRD/SubPRD):")
            for al in allowed_list:
                val = al.get("value", "")
                kind = al.get("kind", "")
                cond = al.get("condition", "")
                prd = al.get("prd_basis", "")
                lines.append(f"  - value={val!r}, kind={kind}")
                lines.append(f"    condition: {cond}")
                lines.append(f"    prd_basis: {prd}")
        forbidden_list = literal_expectations.get("forbidden", [])
        if forbidden_list:
            lines.append("Forbidden literals (must be rejected):")
            for fl in forbidden_list:
                val = fl.get("value", "")
                kind = fl.get("kind", "")
                reason = fl.get("reason", "")
                lines.append(f"  - value={val!r}, kind={kind}")
                lines.append(f"    reason: {reason}")
        lines.append("")

    # Parent I/O
    inputs = node_dict.get("inputs", [])
    outputs = node_dict.get("outputs", [])
    lines.append("Parent Inputs:")
    for inp in inputs:
        lines.append(f"  - {inp.get('name', '')}: {inp.get('type', '')} - {inp.get('description', '')}")
    lines.append("Parent Outputs:")
    for out in outputs:
        lines.append(f"  - {out.get('name', '')}: {out.get('type', '')} - {out.get('description', '')}")

    # Data sources
    data_sources = node_dict.get("data_sources", [])
    if data_sources:
        lines.append("Data Sources:")
        for ds in data_sources:
            lines.append(f"  - {ds.get('name', '')} ({ds.get('category', '')}, {ds.get('access', '')})")

    # Children
    lines.append("")
    lines.append("=" * 60)
    lines.append("CHILDREN — INTERFACES AND DATA OPERATIONS")
    lines.append("=" * 60)

    children = node_dict.get("children", [])
    children_contracts = node_dict.get("children_contracts", {})

    for child in children:
        cname = child.get("name", "")
        contract = children_contracts.get(cname, {})
        lines.append(f"")
        lines.append(f"  [{cname}]")
        lines.append(f"    Purpose: {contract.get('purpose', '')}")
        lines.append(f"    Behavior: {contract.get('behavior', '')}")
        if contract.get("signature"):
            lines.append(f"    Signature: {contract['signature']}")
        if contract.get("inputs"):
            lines.append(f"    Inputs:")
            for inp in contract["inputs"]:
                source = inp.get("source", "unspecified")
                lines.append(f"      - {inp.get('name', '')}: {inp.get('type', '')} (source: {source})")
        if contract.get("outputs"):
            lines.append(f"    Outputs:")
            for out in contract["outputs"]:
                consumer = out.get("consumer", "unspecified")
                lines.append(f"      - {out.get('name', '')}: {out.get('type', '')} (consumer: {consumer})")
        if contract.get("data_operations"):
            lines.append(f"    Data Operations:")
            for op in contract["data_operations"]:
                lines.append(f"      - {op.get('source_name', '')}: {op.get('operation_type', '')} ({op.get('description', '')})")

    # Dataflow edges
    dataflow_edges = node_dict.get("dataflow_edges", [])
    if dataflow_edges:
        lines.append("")
        lines.append("=" * 60)
        lines.append("DECLARED DATAFLOW EDGES - AUTHORITATIVE COMPOSITION CONTRACT")
        lines.append("=" * 60)
        lines.append("")
        lines.append("Each row is a data transfer that the parent implementation must realize.")
        lines.append("Sibling-to-sibling rows describe data dependency only; they must be implemented by the parent:")
        lines.append("the parent calls the source child, stores its output, then passes the value to the target child.")
        lines.append("Children must never call siblings.")
        lines.append("")
        lines.append("| from_node | from_output | to_node | to_input | note |")
        lines.append("|-----------|-------------|---------|----------|------|")
        for e in dataflow_edges:
            lines.append(f"| {e.get('from_node', '')} | {e.get('from_output', '')} | {e.get('to_node', '')} | {e.get('to_input', '')} | {e.get('note', '')} |")

    # Generated code
    lines.append("")
    lines.append("=" * 60)
    lines.append("GENERATED CODE TO VERIFY")
    lines.append("=" * 60)
    lines.append("```python")
    lines.append(code.strip())
    lines.append("```")
    lines.append("")
    lines.append("Apply the verification checklist. Return your verdict as valid JSON.")

    return "\n".join(lines)


def build_verify_system_prompt(order: str) -> str:
    """Build the verify system prompt for old_order or new_order."""
    checklist = """You are a senior code reviewer examining a code submission. The code below was written by another developer. Your job is to review whether the submitted parent function correctly uses the declared child functions — and based on that, judge whether the decomposition (the set of children) is valid.

The decomposition declares a set of child functions. The parent function is supposed to call EACH child directly. Review the code carefully: if any child's name never appears as a DIRECT call in the parent code, the decomposition is INVALID — those children are not actually composed into the parent.

REVIEW CHECKLIST — examine the code and the children list together:

1. RETURN VALUE ORIGIN — Trace every value in every return statement. Each business value must originate from a child function's output or a parent function's input. Acceptable origins include:
   - A variable assigned from a child call: rows = RunQuery(...)
   - A field extracted from a child result: user_id = transaction["user_id"]
   - A parent input parameter: amount, service, etc.
   - A computation from parent inputs: len(content), quantity * 2

   A return value that is a literal (None, True, False, a quoted string, a number, an empty list [], an empty dict {}) is a VIOLATION if it represents data that should come from a child.

2. CHILD COVERAGE — Compare the children list against the actual code. EVERY child's function name must appear as a direct call site in the parent code. If child names are missing from the code (not called by the parent), that is a FAIL — the decomposition claims these children are needed but the parent doesn't use them.

3. DIRECT ACCESS — The code must NOT directly read or write any global variable or data source. All data operations must go through child function calls.

4. NO CROSS CALLS (TREE STRUCTURE) — The decomposition is a tree, not a graph. Each child should only be called by the parent. If the code shows one child calling another child, that is a tree structure violation — siblings do not call each other.

5. DECLARED DATAFLOW CONFORMANCE — Verify that generated code realizes every declared dataflow edge. For child-to-child data dependency, parent must mediate the transfer. If code uses a different source for a child input than the declared edge requires, return cannot_compose with reason "dataflow_conformance_failure".

"""

    # Inject literal policy check
    checklist += LITERAL_POLICY_CHECK + "\n\n"

    if order == "old_order":
        checklist += "If ANY check fails, return status=\"cannot_compose\" with detailed feedback and list which checks failed in failed_checks.\n"
        checklist += "If ALL checks pass, return status=\"ok\" with empty checks marked passed.\n\n"
        checklist += OLD_ORDER_SCHEMA
    else:  # new_order
        checklist += NEW_ORDER_SCHEMA

    return checklist


# ============================================================================
# Consistency analysis
# ============================================================================

def analyze_consistency(parsed: Dict[str, Any], order: str) -> Dict[str, Any]:
    """Check for self-contradiction in the parsed verify response."""
    if order == "old_order":
        top_status = parsed.get("status", "")
    else:
        top_status = parsed.get("final_status", "")

    checks = parsed.get("checks", {})
    df = parsed.get("decomposition_feedback", {}) or {}
    failed_checks = df.get("failed_checks", [])
    requires_redecomp = df.get("requires_redecomposition", False)

    # Check if any individual check failed
    any_check_failed = False
    check_failures = []
    for name, result in checks.items():
        if isinstance(result, dict) and result.get("passed") is False:
            any_check_failed = True
            check_failures.append(name)

    # Also collect checks that are in failed_checks but not in check_failures
    for fc in failed_checks:
        if fc not in check_failures:
            check_obj = checks.get(fc, {})
            if isinstance(check_obj, dict) and check_obj.get("passed") is not False:
                # This is an inconsistency within the response itself
                pass

    # Self-contradiction detection
    is_contradictory = False
    contradiction_type = ""

    if top_status == "ok":
        # Status says ok, but did any check actually fail?
        if failed_checks:
            is_contradictory = True
            contradiction_type = "ok_but_failed_checks_nonempty"
        elif requires_redecomp:
            is_contradictory = True
            contradiction_type = "ok_but_requires_redecomposition"
        elif any_check_failed:
            is_contradictory = True
            contradiction_type = "ok_but_check_passed_false"
    elif top_status == "cannot_compose":
        # Status says cannot_compose, but all checks pass and no failed_checks
        if not failed_checks and not any_check_failed and not requires_redecomp:
            is_contradictory = True
            contradiction_type = "cannot_compose_but_all_checks_pass"
    elif not top_status:
        is_contradictory = True
        contradiction_type = "missing_status_field"

    return {
        "top_level_status": top_status,
        "failed_checks": failed_checks,
        "requires_redecomposition": requires_redecomp,
        "any_check_failed": any_check_failed,
        "check_failures": check_failures,
        "is_self_contradictory": is_contradictory,
        "contradiction_type": contradiction_type,
    }


# ============================================================================
# Main experiment
# ============================================================================

def run_single_verify(
    api_client: APIClient,
    node_dict: Dict,
    code: str,
    order: str,
    literal_expectations: Optional[Dict] = None,
) -> Tuple[Dict[str, Any], str, Dict[str, Any]]:
    """Run a single verify call and return (parsed, raw_response, consistency)."""
    system_prompt = build_verify_system_prompt(order)
    user_prompt = build_verify_prompt_common(node_dict, code, literal_expectations)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    raw_response = _call_llm_with_retry(api_client, messages, max_tokens=1024)
    parsed = _parse_json_response(raw_response)
    consistency = analyze_consistency(parsed, order)

    return parsed, raw_response, consistency


def determine_verdict(
    case_id: str,
    expected: str,
    order: str,
    parsed: Dict[str, Any],
    consistency: Dict[str, Any],
    clean_v2_verdict: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Determine the verdict for a case/order combination."""
    if order == "old_order":
        status_field = parsed.get("status", "")
    else:
        status_field = parsed.get("final_status", "")

    checks = parsed.get("checks", {})
    df = parsed.get("decomposition_feedback", {}) or {}
    failed_checks = df.get("failed_checks", [])
    requires_redecomp = df.get("requires_redecomposition", False)

    any_check_failed = consistency.get("any_check_failed", False)
    is_contradictory = consistency.get("is_self_contradictory", False)
    contradiction_type = consistency.get("contradiction_type", "")

    # Determine if the case passed its expected outcome
    if expected == "accept":
        # Positive case: should be accepted
        if status_field == "ok" and not is_contradictory:
            verdict = "correct_accept"
            passed = True
        elif status_field == "ok" and is_contradictory:
            verdict = "accept_with_contradiction"
            passed = False
        elif status_field == "cannot_compose":
            verdict = "false_rejection"
            passed = False
        else:
            verdict = "ambiguous"
            passed = False
    else:  # expected == "reject"
        # Negative case: should be rejected
        if status_field == "cannot_compose" and not is_contradictory:
            verdict = "correct_reject"
            passed = True
        elif status_field == "cannot_compose" and is_contradictory:
            verdict = "reject_with_contradiction"
            passed = False
        elif status_field == "ok":
            verdict = "false_acceptance"
            passed = False
        else:
            verdict = "ambiguous"
            passed = False

    return {
        "case_id": case_id,
        "expected": expected,
        "order": order,
        "verdict": verdict,
        "passed": passed,
        "top_level_status": status_field,
        "failed_checks": failed_checks,
        "requires_redecomposition": requires_redecomp,
        "any_check_failed": any_check_failed,
        "is_self_contradictory": is_contradictory,
        "contradiction_type": contradiction_type,
    }


def main():
    parser = argparse.ArgumentParser(description="Step2 Verifier Schema-Order Experiment")
    parser.add_argument("--api-key", default=None, help="DeepSeek API key")
    parser.add_argument("--base-url", default=None, help="API base URL")
    parser.add_argument("--model", default="deepseek-chat", help="Model name")
    parser.add_argument("--cases", default=None, help="Comma-separated case IDs to run (default: all)")
    args = parser.parse_args()

    # Setup
    os.makedirs(OUTPUT_BASE, exist_ok=True)
    log_path = _install_run_log(OUTPUT_BASE)

    config = Config()
    if args.api_key:
        config.deepseek_api_key = args.api_key
    if args.base_url:
        config.deepseek_base_url = args.base_url

    api_client = APIClient(config)

    case_ids = args.cases.split(",") if args.cases else list(CASE_DEFS.keys())
    print(f"Running schema-order experiment with cases: {case_ids}")
    print(f"Output: {OUTPUT_BASE}")
    print(f"Clean v2 source: {CLEAN_V2_DIR}")
    print()

    # Load all cases
    cases = {}
    for cid in case_ids:
        print(f"Loading case {cid}...")
        cases[cid] = load_clean_v2_case(cid)
        if "code" not in cases[cid]:
            print(f"  WARNING: No code found for {cid}, skipping")
        else:
            print(f"  Loaded: {cases[cid].get('code_source', 'unknown')}")

    # Run each case with both orders
    all_results = {}

    for cid in case_ids:
        case = cases[cid]
        if "code" not in case:
            continue

        case_dir = os.path.join(OUTPUT_BASE, f"case_{cid}")
        os.makedirs(case_dir, exist_ok=True)

        node_dict = case["node_json"]
        code = case["code"]
        lit_exp = case.get("literal_expectations")

        print(f"\n{'='*60}")
        print(f"Case {cid} (expected: {case['expected']}, mode: {case['mode']})")
        print(f"{'='*60}")

        case_results = {}

        for order in ("old_order", "new_order"):
            print(f"\n  [{order}] Running verify...")
            parsed, raw_response, consistency = run_single_verify(
                api_client, node_dict, code, order, lit_exp
            )

            verdict = determine_verdict(
                cid, case["expected"], order, parsed, consistency,
                case.get("clean_v2_verdict"),
            )

            # Save artifacts
            order_dir = os.path.join(case_dir, order)
            os.makedirs(order_dir, exist_ok=True)
            _save_text(os.path.join(order_dir, "prompt_system.txt"), build_verify_system_prompt(order))
            _save_text(os.path.join(order_dir, "prompt_user.txt"),
                       build_verify_prompt_common(node_dict, code, lit_exp))
            _save_text(os.path.join(order_dir, "response_raw.txt"), raw_response)
            _save_json(os.path.join(order_dir, "parsed_response.json"), parsed)
            _save_json(os.path.join(order_dir, "consistency.json"), consistency)
            _save_json(os.path.join(order_dir, "verdict.json"), verdict)

            case_results[order] = verdict

            status = "CONTRADICTORY" if consistency["is_self_contradictory"] else "CONSISTENT"
            print(f"  [{order}] Status: {verdict['top_level_status']}")
            print(f"  [{order}] Consistency: {status}")
            if consistency["is_self_contradictory"]:
                print(f"  [{order}] Contradiction type: {consistency['contradiction_type']}")
            print(f"  [{order}] Verdict: {verdict['verdict']} ({'PASS' if verdict['passed'] else 'FAIL'})")

        all_results[cid] = case_results

    # Generate results.json
    results = {
        "experiment": "step2_verify_schema_order",
        "model": MODEL_NAME,
        "timestamp": _time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cases": all_results,
    }
    _save_json(os.path.join(OUTPUT_BASE, "results.json"), results)

    # Generate report
    report = generate_report(all_results, cases)
    _save_text(os.path.join(OUTPUT_BASE, "report.md"), report)
    print(f"\n\nReport saved to {os.path.join(OUTPUT_BASE, 'report.md')}")
    print(f"Results saved to {os.path.join(OUTPUT_BASE, 'results.json')}")


def generate_report(all_results: Dict, cases: Dict) -> str:
    """Generate markdown report comparing old_order vs new_order."""
    lines = [
        "# Step2 Verifier Schema-Order Experiment Report",
        "",
        f"**Model**: {MODEL_NAME}",
        f"**Date**: {_time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Hypothesis",
        "",
        "Reordering the verify JSON schema from `status -> checks -> decomposition_feedback`",
        "to `checks -> decomposition_feedback -> final_status` will reduce self-contradictory",
        "outputs where status='ok' but failed_checks is non-empty.",
        "",
        "## Cases",
        "",
        "| Case | Expected | Mode | Description |",
        "|------|----------|------|-------------|",
    ]

    case_descs = {
        "P1": ("accept", "full_generate", "Unsupported command branch literal"),
        "P2": ("accept", "full_generate", "Empty list PRD literal"),
        "P3": ("accept", "full_generate", "Conditional dispatch, no literals"),
        "N1": ("reject", "verifier_only", "Hardcoded runtime ID"),
        "N2a": ("reject", "verifier_only", "Literal substitutes child output"),
        "N2b": ("accept", "full_generate", "Full generate, child output required (positive control)"),
        "N3a": ("reject", "verifier_only", "Runtime status hardcoded"),
        "N3b": ("accept", "full_generate", "Full generate, status from child (positive control)"),
        "N4": ("reject", "verifier_only", "Missing capability masked by literal"),
        "N5": ("reject", "full_generate", "Sibling call violation (key case)"),
    }

    for cid in sorted(all_results.keys()):
        exp, mode, desc = case_descs.get(cid, ("", "", ""))
        lines.append(f"| {cid} | {exp} | {mode} | {desc} |")

    lines.append("")

    # Per-case comparison table
    lines.append("## Per-Case Results")
    lines.append("")
    lines.append("| Case | Expected | Old Status | New Status | Old Contradictory | New Contradictory | Old Verdict | New Verdict |")
    lines.append("|------|----------|------------|------------|-------------------|-------------------|-------------|-------------|")

    old_contradictions = 0
    new_contradictions = 0
    old_correct = 0
    new_correct = 0
    n5_old_ok = False
    n5_new_ok = False
    n5_old_contradictory = False
    n5_new_contradictory = False

    for cid in sorted(all_results.keys()):
        case = all_results[cid]
        old = case.get("old_order", {})
        new = case.get("new_order", {})

        old_status = old.get("top_level_status", "N/A")
        new_status = new.get("top_level_status", "N/A")
        old_contra = "YES" if old.get("is_self_contradictory") else "no"
        new_contra = "YES" if new.get("is_self_contradictory") else "no"
        old_verd = old.get("verdict", "N/A")
        new_verd = new.get("verdict", "N/A")
        expected = cases[cid].get("expected", "")

        lines.append(f"| {cid} | {expected} | {old_status} | {new_status} | {old_contra} | {new_contra} | {old_verd} | {new_verd} |")

        if old.get("is_self_contradictory"):
            old_contradictions += 1
        if new.get("is_self_contradictory"):
            new_contradictions += 1
        if old.get("passed"):
            old_correct += 1
        if new.get("passed"):
            new_correct += 1

        if cid == "N5":
            n5_old_ok = old.get("top_level_status") == "ok"
            n5_new_ok = new.get("top_level_status") == "ok"
            n5_old_contradictory = old.get("is_self_contradictory", False)
            n5_new_contradictory = new.get("is_self_contradictory", False)

    total = len(all_results)
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Old Order | New Order |")
    lines.append(f"|--------|-----------|-----------|")
    lines.append(f"| Self-contradictions | {old_contradictions}/{total} | {new_contradictions}/{total} |")
    lines.append(f"| Correct verdicts | {old_correct}/{total} | {new_correct}/{total} |")

    lines.append("")
    lines.append("## Key Findings")
    lines.append("")

    # N5 focus
    lines.append("### N5 (Sibling Call Violation — Key Case)")
    lines.append("")
    lines.append(f"- **Old order**: status=`{all_results.get('N5', {}).get('old_order', {}).get('top_level_status', 'N/A')}`, contradictory={n5_old_contradictory}")
    lines.append(f"- **New order**: final_status=`{all_results.get('N5', {}).get('new_order', {}).get('top_level_status', 'N/A')}`, contradictory={n5_new_contradictory}")

    if n5_old_contradictory and not n5_new_contradictory:
        lines.append("- **Result**: Schema reordering FIXED the N5 contradiction.")
    elif n5_old_contradictory and n5_new_contradictory:
        lines.append("- **Result**: Schema reordering did NOT fix the N5 contradiction.")
    elif not n5_old_contradictory:
        lines.append("- **Result**: N5 was not contradictory in old_order (unexpected).")

    lines.append("")

    # Positive false rejection check
    lines.append("### Positive False Rejection Check")
    lines.append("")
    positives = ["P1", "P2", "P3", "N2b", "N3b"]
    new_false_rejects = []
    for pid in positives:
        if pid in all_results:
            new_verd = all_results[pid].get("new_order", {}).get("verdict", "")
            if new_verd == "false_rejection":
                new_false_rejects.append(pid)
    if new_false_rejects:
        lines.append(f"- **WARNING**: new_order introduced false rejections on: {', '.join(new_false_rejects)}")
    else:
        lines.append("- No false rejections on positive cases in new_order.")

    lines.append("")

    # Negative rejection check
    lines.append("### Negative Rejection Check")
    lines.append("")
    negatives = ["N1", "N2a", "N3a", "N4", "N5"]
    new_false_accepts = []
    for nid in negatives:
        if nid in all_results:
            new_verd = all_results[nid].get("new_order", {}).get("verdict", "")
            if new_verd == "false_acceptance":
                new_false_accepts.append(nid)
    if new_false_accepts:
        lines.append(f"- **WARNING**: new_order failed to reject: {', '.join(new_false_accepts)}")
    else:
        lines.append("- All negative cases correctly rejected in new_order.")

    lines.append("")

    # Conclusion
    lines.append("## Conclusion")
    lines.append("")

    if new_contradictions < old_contradictions and not new_false_rejects and not new_false_accepts:
        lines.append("Schema reordering **improved** consistency without introducing regressions.")
    elif new_contradictions == old_contradictions and not new_false_rejects and not new_false_accepts:
        lines.append("Schema reordering had **no effect** on consistency. Field order alone is insufficient; may need parser consistency override.")
    elif new_contradictions > old_contradictions:
        lines.append("Schema reordering **increased** contradictions. This approach is counterproductive.")
    else:
        lines.append("Mixed results. See per-case details above.")

    lines.append("")
    lines.append("---")
    lines.append("*Stop rule: single pass, no prompt tuning, no MVP modification.*")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
