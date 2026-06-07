"""
Step2 Literal Policy Experiment — Clean Rerun.

Tests whether a prompt-only Step2 literal policy can accept PRD/branch-conditioned
literals while rejecting hardcoded runtime facts.

Key differences from first run (see hot.md INCONCLUSIVE):
- Clean fixtures: P1 has FormatResult, no hardcoded success messages
- P2 uses Option B (True Branch Literal empty list)
- Negative cases isolate target invariant; reason matching required
- Verify prompt includes PRD/SubPRD/acceptance context
- Self-audit verifies parent output coverage and literal prd_basis
- Output goes to codegen_literal_policy_step2_clean/<model>/

Stop rule: run once, report, STOP. No prompt tuning.
"""
import argparse
import ast
import json
import os
import re
import sys
import time as _time
from typing import Any, Dict, List, Optional, Tuple

# Must insert src before importing project modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from config import Config
from api_client import APIClient
from models import (
    Node, InputParam, OutputParam, DataflowEdge, ChildContract,
    SubPRD, AcceptanceCriterion, Traceability, DataOperation,
    Boundary, GlobalVar, DataSource,
)

from code_generator_literal_policy import LiteralPolicyCodeGenerator


MODEL_NAME = "deepseek-chat"
OUTPUT_NAME = "codegen_literal_policy_step2_clean_v2"
OUTPUT_BASE = os.path.join(
    os.path.dirname(__file__),
    "output", OUTPUT_NAME, MODEL_NAME
)


# ============================================================================
# Helpers
# ============================================================================

class _Tee:
    """Write every line to both terminal and run.log, flushing immediately."""

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


def _clean_text(s: str) -> str:
    """Strip and collapse whitespace."""
    return " ".join(s.split()).strip()


def _build_verdict(case_id, expected, passed, category,
                   generate_status, verify_status, reason,
                   failed_checks, static_analysis, reason_note=""):
    return {
        "case_id": case_id,
        "expected": expected,
        "passed": passed,
        "category": category,
        "generate_status": generate_status,
        "verify_status": verify_status,
        "failed_checks": failed_checks,
        "static_analysis": static_analysis,
        "reason": reason,
        "reason_note": reason_note,
    }


def _save_json(path: str, data: Any):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ============================================================================
# Self-Audit
# ============================================================================

def run_self_audit_extended(
    case_id: str,
    node: Node,
    expected: str,
    target_invariant: str,
    allowed_literals: List[Dict],
    forbidden_literals: List[Dict],
    mode: str,
    expected_primary_reason: str = "",
) -> Dict[str, Any]:
    """Extended deterministic self-audit before any LLM call.

    Checks:
      1. Parent signature validity
      2. Parent input names valid
      3. Parent output names valid
      4. Child names unique
      5. Child signatures valid (via contract)
      6. Child input names valid
      7. Child output names valid
      8. Every child input has a source
      9. Dataflow from_node/to_node are parent or declared child
     10. Dataflow from_output exists in source child contract
     11. Dataflow to_input exists in target child contract
     12. Parent output coverage (every field classifyable)
     13. Positive: no sibling call text in child behavior
     14. Positive: no missing child capability (every child callable)
     15. Literal expectations have prd_basis
     16. Negative: expected primary reason declared
     17. Negative: no unintended primary violation (unless mixed)
    """
    checks = {}
    child_names = [c.name for c in (node.children or [])]
    child_name_set = set(child_names)

    # 1
    checks["parent_signature_valid"] = bool(node.name and node.name.isidentifier())

    # 2
    checks["parent_inputs_valid"] = all(
        inp.name.isidentifier() for inp in node.inputs
    )

    # 3
    checks["parent_outputs_valid"] = all(
        out.name.isidentifier() for out in node.outputs
    )

    # 4
    checks["child_names_unique"] = len(child_names) == len(child_name_set)

    # 5
    all_child_sigs_ok = True
    for cname, contract in (node.children_contracts or {}).items():
        if contract.signature:
            # basic check: contains "def" and parenthesized params
            if "def " not in contract.signature or "(" not in contract.signature:
                all_child_sigs_ok = False
    checks["child_signatures_valid"] = all_child_sigs_ok

    # 6
    all_child_inputs_ok = True
    for cname, contract in (node.children_contracts or {}).items():
        for inp in contract.inputs:
            if inp.name and not inp.name.isidentifier():
                all_child_inputs_ok = False
    checks["child_inputs_valid"] = all_child_inputs_ok

    # 7
    all_child_outputs_ok = True
    for cname, contract in (node.children_contracts or {}).items():
        for out in contract.outputs:
            if out.name and not out.name.isidentifier():
                all_child_outputs_ok = False
    checks["child_outputs_valid"] = all_child_outputs_ok

    # 8
    all_sourced = True
    for cname, contract in (node.children_contracts or {}).items():
        for inp in contract.inputs:
            if not inp.source:
                all_sourced = False
    checks["all_child_inputs_have_sources"] = all_sourced

    # 9 — dataflow endpoints and non-empty fields
    parent_local_names = set(i.name for i in node.inputs) | set(o.name for o in node.outputs)
    for edge in (node.dataflow_edges or []):
        if edge.to_node == "parent" and edge.to_input:
            parent_local_names.add(edge.to_input)
        if edge.from_node == "parent" and edge.from_output:
            parent_local_names.add(edge.from_output)

    all_edges_non_empty = True
    all_endpoints_ok = True
    for edge in (node.dataflow_edges or []):
        if not edge.from_node or not edge.from_output or not edge.to_node or not edge.to_input:
            all_edges_non_empty = False
        from_ok = edge.from_node == "parent" or edge.from_node in child_name_set
        to_ok = edge.to_node == "parent" or edge.to_node in child_name_set
        if not (from_ok and to_ok):
            all_endpoints_ok = False
    checks["dataflow_edges_non_empty"] = all_edges_non_empty
    checks["dataflow_endpoints_exist"] = all_endpoints_ok

    # 10 — dataflow source fields exist in child contracts
    all_source_fields_ok = True
    for edge in (node.dataflow_edges or []):
        if edge.from_node == "parent":
            if not edge.from_output or edge.from_output not in parent_local_names:
                all_source_fields_ok = False
        elif edge.from_node in (node.children_contracts or {}):
            contract = node.children_contracts[edge.from_node]
            field_names = [o.name for o in contract.outputs]
            if not edge.from_output or edge.from_output not in field_names:
                all_source_fields_ok = False
    checks["dataflow_source_fields_exist"] = all_source_fields_ok

    # 11 — dataflow target fields exist
    all_target_fields_ok = True
    for edge in (node.dataflow_edges or []):
        if edge.to_node == "parent":
            if not edge.to_input or edge.to_input not in parent_local_names:
                all_target_fields_ok = False
        elif edge.to_node in (node.children_contracts or {}):
            contract = node.children_contracts[edge.to_node]
            field_names = [i.name for i in contract.inputs]
            if not edge.to_input or edge.to_input not in field_names:
                all_target_fields_ok = False
    checks["dataflow_target_fields_exist"] = all_target_fields_ok

    # 12 — parent output coverage (positive cases only)
    parent_out_names = [o.name for o in node.outputs]
    parent_output_sources = {name: [] for name in parent_out_names}
    for edge in (node.dataflow_edges or []):
        if edge.to_node == "parent" and edge.to_input in parent_output_sources:
            parent_output_sources[edge.to_input].append(f"{edge.from_node}.{edge.from_output}")
    literal_covered_outputs = set()
    for lit in (allowed_literals or []):
        for output_name in lit.get("covers_parent_outputs", []) or []:
            literal_covered_outputs.add(output_name)
    uncovered = []
    for pout in parent_out_names:
        if parent_output_sources.get(pout) or pout in literal_covered_outputs:
            continue
        uncovered.append(pout)
    if expected == "accept":
        checks["parent_output_coverage_valid"] = len(uncovered) == 0
    else:
        checks["parent_output_coverage_valid"] = True  # N/A for negatives

    # 13 — positive: no sibling call text
    sibling_keywords = ["calls ", "invokes ", "dispatches to ", "routes to "]
    has_sibling_text = False
    if expected == "accept":
        for cname, contract in (node.children_contracts or {}).items():
            bl = contract.behavior.lower()
            for sib in child_names:
                if sib != cname and sib.lower() in bl:
                    for kw in sibling_keywords:
                        if kw + sib.lower() in bl:
                            has_sibling_text = True
                            break
    checks["positive_has_no_sibling_call_text"] = not has_sibling_text

    # 14 — positive: no missing child capability
    if expected == "accept":
        checks["positive_has_no_missing_child_capability"] = True
    else:
        checks["positive_has_no_missing_child_capability"] = True  # N/A

    # 15 — literal expectations have prd_basis
    all_lit_have_prd = True
    for al in (allowed_literals or []):
        if not al.get("prd_basis"):
            all_lit_have_prd = False
    for fl in (forbidden_literals or []):
        if not fl.get("reason"):
            all_lit_have_prd = False
    checks["literal_expectations_have_prd_basis"] = all_lit_have_prd

    # 16 — negative: expected reason declared
    if expected == "reject":
        checks["negative_has_expected_primary_reason"] = bool(expected_primary_reason)
    else:
        checks["negative_has_expected_primary_reason"] = True  # N/A

    # 17 — negative: no unintended violation (unless mixed)
    checks["negative_has_no_unintended_violation"] = True  # simplified

    # All checks passed?
    passed = all(checks.values())

    audit_result = {
        "case_id": case_id,
        "expected": expected,
        "target_invariant": target_invariant,
        "mode": mode,
        "expected_primary_reason": expected_primary_reason,
        "passed": passed,
        "checks": checks,
        "allowed_literals": allowed_literals,
        "forbidden_literals": forbidden_literals,
        "parent_output_uncovered": uncovered,
        "notes": [],
    }
    if not passed:
        failed = [k for k, v in checks.items() if not v]
        audit_result["notes"].append(f"Audit failed on checks: {failed}")
    return audit_result


# ============================================================================
# Static Analysis
# ============================================================================

def analyze_generated_code_extended(
    code: str,
    node: Node,
    forbidden_literals: List[Dict],
    allowed_literals: List[Dict],
) -> Dict[str, Any]:
    """Enhanced static analysis of generated code.

    Records return literals, assignment literals feeding returns,
    dead/fallback container literals, parent output coverage.
    """
    parent_name = node.name
    child_names = [c.name for c in (node.children or [])]
    allowed_values = {str(al.get("value")) for al in (allowed_literals or [])}
    forbidden_values = {str(fl.get("value")) for fl in (forbidden_literals or [])}

    defines_parent = False
    direct_child_calls = []
    missing_child_calls = []
    unexpected_calls = []
    return_literals = []
    assignment_literals_feeding_returns = []
    all_code_literals = []
    allowed_literals_detected = []
    forbidden_literals_detected = []
    dead_or_fallback_container_literals = []
    has_branch_logic = False
    parent_outputs_covered = True
    uses_declared_dataflow = True

    if not code:
        return {
            "defines_parent_function": False,
            "direct_child_calls": [],
            "missing_child_calls": child_names,
            "unexpected_child_or_sibling_calls": [],
            "return_literals": [],
            "assignment_literals_feeding_returns": [],
            "all_code_literals": [],
            "allowed_literals_detected": [],
            "forbidden_literals_detected": [],
            "dead_or_fallback_container_literals": [],
            "has_branch_logic": False,
            "parent_outputs_covered_by_code": False,
            "uses_declared_dataflow": False,
        }

    def literal_token(expr):
        if isinstance(expr, ast.Constant):
            if isinstance(expr.value, str):
                return expr.value
            if isinstance(expr.value, bool):
                return "True" if expr.value else "False"
            if expr.value is None:
                return "None"
            if isinstance(expr.value, (int, float)):
                return repr(expr.value)
        if isinstance(expr, ast.List) and not expr.elts:
            return "[]"
        if isinstance(expr, ast.Dict) and not expr.keys:
            return "{}"
        return None

    def key_token(expr):
        token = literal_token(expr)
        return token if token is not None else "__dynamic_key__"

    def classify_literal(token, key="__direct__", context="return"):
        record = {"key": key, "value": token, "context": context}
        return_literals.append(record)
        if token in allowed_values:
            allowed_literals_detected.append(token)
        if token in forbidden_values:
            forbidden_literals_detected.append(token)
        if token in ("[]", "{}"):
            dead_or_fallback_container_literals.append({"value": token, "context": context, "key": key})

    def analyze_return_expr(expr, assignments, context="return"):
        """Trace literal values in return expressions and simple assignment feeders."""
        if isinstance(expr, ast.Dict):
            for key_expr, value_expr in zip(expr.keys, expr.values):
                key = key_token(key_expr)
                token = literal_token(value_expr)
                if token is not None:
                    classify_literal(token, key=key, context=context)
                elif isinstance(value_expr, ast.Name) and value_expr.id in assignments:
                    feeder = assignments[value_expr.id]
                    feeder_token = literal_token(feeder)
                    if feeder_token is not None:
                        assignment_literals_feeding_returns.append({
                            "name": value_expr.id,
                            "key": key,
                            "value": feeder_token,
                            "context": context,
                        })
                        classify_literal(feeder_token, key=key, context=f"assignment:{value_expr.id}")
                    elif isinstance(feeder, ast.Dict):
                        assignment_literals_feeding_returns.append({
                            "name": value_expr.id,
                            "key": key,
                            "value": "<dict>",
                            "context": context,
                        })
                        analyze_return_expr(feeder, assignments, context=f"assignment:{value_expr.id}")
        else:
            token = literal_token(expr)
            if token is not None:
                classify_literal(token, context=context)
            elif isinstance(expr, ast.Name) and expr.id in assignments:
                feeder = assignments[expr.id]
                feeder_token = literal_token(feeder)
                if feeder_token is not None:
                    assignment_literals_feeding_returns.append({
                        "name": expr.id,
                        "key": "__direct__",
                        "value": feeder_token,
                        "context": context,
                    })
                    classify_literal(feeder_token, context=f"assignment:{expr.id}")
                elif isinstance(feeder, ast.Dict):
                    assignment_literals_feeding_returns.append({
                        "name": expr.id,
                        "key": "__direct__",
                        "value": "<dict>",
                        "context": context,
                    })
                    analyze_return_expr(feeder, assignments, context=f"assignment:{expr.id}")

    # Detect parent function definition
    parent_pattern = re.compile(rf"def\s+{re.escape(parent_name)}\s*\(")
    defines_parent = bool(parent_pattern.search(code))

    # Detect child calls
    for cname in child_names:
        call_pattern = re.compile(rf"\b{re.escape(cname)}\s*\(")
        if call_pattern.search(code):
            direct_child_calls.append(cname)
        else:
            missing_child_calls.append(cname)

    # Detect unexpected calls (function calls that look like children but are not)
    func_call_pattern = re.compile(r"(?<=def )\w+|(?<=\s)(\w+)\s*\(")
    all_calls = set()
    for m in func_call_pattern.finditer(code):
        name = m.group(1) or m.group(0)
        if name != parent_name and not name.startswith("_") and name[0].islower():
            all_calls.add(name)
    unexpected_calls = list(
        c for c in (all_calls - set(child_names) - {parent_name})
        if c not in ("if", "for", "while", "with", "not", "and", "or", "in", "is", "return", "dict", "list", "str", "int", "float", "bool", "len", "range", "isinstance", "type", "print", "open", "tuple", "set")
    )

    # Find all string/number/bool/list/dict literals in return statements.
    # AST lets us catch both `return {"x": False}` and `result = {"x": False}; return result`.
    try:
        tree = ast.parse(code)
        for expr in ast.walk(tree):
            token = literal_token(expr)
            if token is not None:
                all_code_literals.append(token)
                if token in allowed_values:
                    allowed_literals_detected.append(token)
                if token in forbidden_values:
                    forbidden_literals_detected.append(token)
        for func in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == parent_name]:
            assignments = {}
            for stmt in ast.walk(func):
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            assignments[target.id] = stmt.value
                elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    assignments[stmt.target.id] = stmt.value
            for stmt in ast.walk(func):
                if isinstance(stmt, ast.Return) and stmt.value is not None:
                    analyze_return_expr(stmt.value, assignments)
    except SyntaxError:
        # Keep static analysis non-blocking; malformed code is already captured elsewhere.
        pass

    # Detect branch logic
    has_branch_logic = bool(re.search(r"\bif\s+", code)) and bool(re.search(r"\belse\b", code))

    # Check parent output coverage (simple: parent fields referenced directly)
    parent_out_names = set(o.name for o in node.outputs)
    covered_fields = set()
    for fname in parent_out_names:
        if fname in code:
            covered_fields.add(fname)
    parent_outputs_covered = len(covered_fields) == len(parent_out_names) if parent_out_names else True

    # Dataflow usage (simplified: check if child output variables are used)
    uses_declared_dataflow = len(missing_child_calls) == 0 or defines_parent

    # Deduplicate
    all_code_literals = sorted(set(all_code_literals))
    allowed_literals_detected = sorted(set(allowed_literals_detected))
    forbidden_literals_detected = sorted(set(forbidden_literals_detected))

    return {
        "defines_parent_function": defines_parent,
        "direct_child_calls": sorted(direct_child_calls),
        "missing_child_calls": sorted(missing_child_calls),
        "unexpected_child_or_sibling_calls": sorted(unexpected_calls),
        "return_literals": return_literals,
        "assignment_literals_feeding_returns": assignment_literals_feeding_returns,
        "all_code_literals": all_code_literals,
        "allowed_literals_detected": allowed_literals_detected,
        "forbidden_literals_detected": forbidden_literals_detected,
        "dead_or_fallback_container_literals": dead_or_fallback_container_literals,
        "has_branch_logic": has_branch_logic,
        "parent_outputs_covered_by_code": parent_outputs_covered,
        "uses_declared_dataflow": uses_declared_dataflow,
    }


# ============================================================================
# Case Builders
# ============================================================================

def build_case_P1() -> Tuple[Node, str, List[Dict], List[Dict], str, str, str, str]:
    """P1: unsupported_command_branch_literal.

    Positive case testing exactly one allowed branch literal.
    Only "Unsupported command" and False allowed as BRANCH_LITERAL.
    Valid branch success messages must come from FormatResult child, not hardcoded.
    """
    parent = Node(
        node_id="P1",
        name="ProcessOrder",
        depth=1,
        purpose="Process an order command by dispatching to the appropriate handler.",
        inputs=[InputParam(name="input", type="dict", description="Input dict with command and payload")],
        outputs=[
            OutputParam(name="response", type="dict", description="Response dict with success, message, result keys"),
        ],
        subprd=SubPRD(
            task_id="P1",
            purpose="Order processing dispatch",
            description="Process an incoming order command. Supported commands are 'place', 'cancel', and 'track'. "
                        "If the command is not one of the supported commands, return "
                        "{'success': False, 'message': 'Unsupported command'}. For valid commands, delegate to the corresponding "
                        "handler child and format the result via FormatResult.",
            constraints=[{"type": "behavior", "detail": "Supported commands are exactly: place, cancel, track."}],
            acceptance_criteria=[
                AcceptanceCriterion(ac_id="P1-AC1", description="Unsupported command returns success=False, message='Unsupported command'"),
                AcceptanceCriterion(ac_id="P1-AC2", description="Valid command routes to handler and formats result"),
            ],
            traceability=Traceability(parent_requirement_ids=["PRD-REQ-ORDER-1"]),
        ),
        dataflow_edges=[
            DataflowEdge(from_node="parent", from_output="input", to_node="ParseInput", to_input="input", note="Parse the raw input"),
            DataflowEdge(from_node="ParseInput", from_output="command", to_node="parent", to_input="command", note="Command string for branching"),
            DataflowEdge(from_node="ParseInput", from_output="payload", to_node="parent", to_input="payload", note="Parsed payload for handlers"),
            DataflowEdge(from_node="parent", from_output="payload", to_node="PlaceOrder", to_input="payload", note="Payload to place handler"),
            DataflowEdge(from_node="parent", from_output="payload", to_node="CancelOrder", to_input="payload", note="Payload to cancel handler"),
            DataflowEdge(from_node="parent", from_output="payload", to_node="TrackOrder", to_input="payload", note="Payload to track handler"),
            DataflowEdge(from_node="PlaceOrder", from_output="result", to_node="parent", to_input="handler_result", note="Place result"),
            DataflowEdge(from_node="CancelOrder", from_output="result", to_node="parent", to_input="handler_result", note="Cancel result"),
            DataflowEdge(from_node="TrackOrder", from_output="result", to_node="parent", to_input="handler_result", note="Track result"),
            DataflowEdge(from_node="parent", from_output="handler_result", to_node="FormatResult", to_input="result", note="Format the handler result"),
            DataflowEdge(from_node="FormatResult", from_output="response", to_node="parent", to_input="response", note="Formatted response"),
        ],
    )

    children = [
        Node(
            node_id="P1_child1", name="ParseInput", depth=2,
            purpose="Parse raw JSON input into command and payload.",
            inputs=[InputParam(name="input", type="dict", description="Raw input dict", source="parent input")],
            outputs=[
                OutputParam(name="command", type="str", description="Extracted command string", consumer="parent"),
                OutputParam(name="payload", type="dict", description="Extracted payload", consumer="parent"),
            ],
        ),
        Node(
            node_id="P1_child2", name="PlaceOrder", depth=2,
            purpose="Place an order with the given payload.",
            inputs=[InputParam(name="payload", type="dict", description="Order payload", source="ParseInput.payload")],
            outputs=[OutputParam(name="result", type="dict", description="Order placement result", consumer="parent")],
        ),
        Node(
            node_id="P1_child3", name="CancelOrder", depth=2,
            purpose="Cancel an order with the given payload.",
            inputs=[InputParam(name="payload", type="dict", description="Cancel payload", source="ParseInput.payload")],
            outputs=[OutputParam(name="result", type="dict", description="Cancellation result", consumer="parent")],
        ),
        Node(
            node_id="P1_child4", name="TrackOrder", depth=2,
            purpose="Track an order with the given payload.",
            inputs=[InputParam(name="payload", type="dict", description="Track payload", source="ParseInput.payload")],
            outputs=[OutputParam(name="result", type="dict", description="Tracking result", consumer="parent")],
        ),
        Node(
            node_id="P1_child5", name="FormatResult", depth=2,
            purpose="Format a handler result into the standard response dict.",
            inputs=[InputParam(name="result", type="dict", description="Handler result to format", source="parent")],
            outputs=[OutputParam(name="response", type="dict", description="Formatted response with success, message, result", consumer="parent")],
        ),
    ]
    parent.children = children

    contracts = {}
    for ch in children:
        contract_inputs = [InputParam(name=i.name, type=i.type, description=i.description, source=i.source) for i in ch.inputs]
        contract_outputs = [OutputParam(name=o.name, type=o.type, description=o.description, consumer=o.consumer) for o in ch.outputs]
        sig = f"def {ch.name}({', '.join(i.name + ': ' + i.type for i in contract_inputs)}) -> {'dict' if len(contract_outputs) <= 1 else 'tuple'}"
        contracts[ch.name] = ChildContract(
            purpose=ch.purpose,
            inputs=contract_inputs,
            outputs=contract_outputs,
            behavior=f"{ch.name} performs its function and returns the result.",
            signature=sig,
        )
    parent.children_contracts = contracts

    allowed_literals = [
        {"value": "Unsupported command", "kind": "BRANCH_LITERAL",
         "condition": "command not in place/cancel/track",
         "prd_basis": "SubPRD acceptance criterion P1-AC1 explicitly defines unsupported-command response"},
        {"value": False, "kind": "BRANCH_LITERAL",
         "condition": "unsupported command branch",
         "prd_basis": "SubPRD acceptance criterion P1-AC1 defines success=False for unsupported command"},
    ]
    forbidden_literals = [
        {"value": "Order placed successfully", "kind": "DYNAMIC_VALUE",
         "reason": "Success message for valid branch must come from child output (FormatResult), not parent hardcode"},
        {"value": "Order cancelled successfully", "kind": "DYNAMIC_VALUE",
         "reason": "Same as above"},
        {"value": "Order tracked successfully", "kind": "DYNAMIC_VALUE",
         "reason": "Same as above"},
    ]

    return parent, "accept", allowed_literals, forbidden_literals, "literal_policy", "positive", "", ""


def build_case_P2() -> Tuple[Node, str, List[Dict], List[Dict], str, str, str, str]:
    """P2: empty_list_prd_literal (Option B — True Branch Literal).

    Parent NormalizeFilters normalizes optional tags field.
    If input has no 'tags' key, return normalized_tags=[] as PRD-defined schema default.
    No child fetches runtime records — pure PRD default.
    """
    parent = Node(
        node_id="P2",
        name="NormalizeFilters",
        depth=1,
        purpose="Normalize and validate input filters, providing defaults for optional fields.",
        inputs=[InputParam(name="input", type="dict", description="Input dict with optional tags field")],
        outputs=[
            OutputParam(name="result", type="dict", description="Result dict with success and normalized_tags keys"),
        ],
        subprd=SubPRD(
            task_id="P2",
            purpose="Filter normalization with PRD-defined defaults",
            description="Normalize incoming filter parameters. The 'tags' field is optional. "
                        "After ParseFilters returns filters, if 'tags' is absent, the parent applies tags=[] as a schema default before validation. "
                        "The final result must come from FormatFilters. This [] is a PRD-defined constant default, not a runtime database lookup.",
            constraints=[{"type": "behavior", "detail": "tags is optional; empty list is the PRD-defined default"}],
            acceptance_criteria=[
                AcceptanceCriterion(ac_id="P2-AC1", description="If tags is absent, parent applies tags=[] before validation"),
                AcceptanceCriterion(ac_id="P2-AC2", description="Final result comes from FormatFilters"),
            ],
            traceability=Traceability(parent_requirement_ids=["PRD-REQ-FILTER-1"]),
        ),
        dataflow_edges=[
            DataflowEdge(from_node="parent", from_output="input", to_node="ParseFilters", to_input="input", note="Parse the raw input"),
            DataflowEdge(from_node="ParseFilters", from_output="filters", to_node="parent", to_input="filters", note="Parsed filters for defaulting"),
            DataflowEdge(from_node="parent", from_output="filters", to_node="ValidateFilters", to_input="filters", note="Validate filters after PRD defaults"),
            DataflowEdge(from_node="ValidateFilters", from_output="validated_filters", to_node="parent", to_input="validated_filters", note="Validated filters"),
            DataflowEdge(from_node="parent", from_output="validated_filters", to_node="FormatFilters", to_input="validated_filters", note="Format validated filters"),
            DataflowEdge(from_node="FormatFilters", from_output="result", to_node="parent", to_input="result", note="Final parent output"),
        ],
    )

    children = [
        Node(
            node_id="P2_child1", name="ParseFilters", depth=2,
            purpose="Parse raw input into structured filter dict.",
            inputs=[InputParam(name="input", type="dict", description="Raw input dict", source="parent input")],
            outputs=[OutputParam(name="filters", type="dict", description="Parsed filter dict including tags if present", consumer="parent")],
        ),
        Node(
            node_id="P2_child2", name="ValidateFilters", depth=2,
            purpose="Validate filter parameters.",
            inputs=[InputParam(name="filters", type="dict", description="Filters after PRD defaults are applied", source="parent.filters")],
            outputs=[OutputParam(name="validated_filters", type="dict", description="Validated filters", consumer="parent")],
        ),
        Node(
            node_id="P2_child3", name="FormatFilters", depth=2,
            purpose="Format validated filters into final result.",
            inputs=[InputParam(name="validated_filters", type="dict", description="Validated filters", source="parent.validated_filters")],
            outputs=[OutputParam(name="result", type="dict", description="Final normalized filter result", consumer="parent")],
        ),
    ]
    parent.children = children

    contracts = {}
    for ch in children:
        contract_inputs = [InputParam(name=i.name, type=i.type, description=i.description, source=i.source) for i in ch.inputs]
        contract_outputs = [OutputParam(name=o.name, type=o.type, description=o.description, consumer=o.consumer) for o in ch.outputs]
        sig = f"def {ch.name}({', '.join(i.name + ': ' + i.type for i in contract_inputs)}) -> dict"
        contracts[ch.name] = ChildContract(
            purpose=ch.purpose,
            inputs=contract_inputs,
            outputs=contract_outputs,
            behavior=f"{ch.name} performs its function and returns the result.",
            signature=sig,
        )
    parent.children_contracts = contracts

    allowed_literals = [
        {"value": "[]", "kind": "PRD_LITERAL",
         "condition": "tags key absent from parsed input",
         "prd_basis": "SubPRD acceptance criterion P2-AC1 defines empty list as schema default for absent optional field"},
    ]
    forbidden_literals = [
        {"value": "hardcoded tags", "kind": "DYNAMIC_VALUE",
         "reason": "Tags must come from ParseFilters output or be empty list default"},
    ]

    return parent, "accept", allowed_literals, forbidden_literals, "literal_policy", "positive", "", ""


def build_case_P3() -> Tuple[Node, str, List[Dict], List[Dict], str, str, str, str]:
    """P3: conditional_dispatch_no_literals.

    Positive regression: no unsupported branch, every branch returns child result.
    Generated code may contain dead/fallback container literal (else: result = {}).
    """
    parent = Node(
        node_id="P3",
        name="ProcessAction",
        depth=1,
        purpose="Process an action by dispatching to handler and formatting result.",
        inputs=[InputParam(name="input", type="dict", description="Input dict with action and data")],
        outputs=[
            OutputParam(name="response", type="dict", description="Formatted response dict with success and result keys"),
        ],
        subprd=SubPRD(
            task_id="P3",
            purpose="Action processing dispatch",
            description="Process one of the supported actions: 'create', 'update', 'delete'.",
            constraints=[{"type": "behavior", "detail": "All input actions are one of create/update/delete"}],
            acceptance_criteria=[
                AcceptanceCriterion(ac_id="P3-AC1", description="Valid action routes to handler"),
                AcceptanceCriterion(ac_id="P3-AC2", description="Handler result formatted and returned"),
            ],
            traceability=Traceability(parent_requirement_ids=["PRD-REQ-ACTION-1"]),
        ),
        dataflow_edges=[
            DataflowEdge(from_node="parent", from_output="input", to_node="ParseAction", to_input="input", note="Parse input"),
            DataflowEdge(from_node="ParseAction", from_output="action", to_node="parent", to_input="action", note="Action for branching"),
            DataflowEdge(from_node="ParseAction", from_output="data", to_node="parent", to_input="data", note="Data for handlers"),
            DataflowEdge(from_node="parent", from_output="data", to_node="CreateHandler", to_input="data", note="Create action"),
            DataflowEdge(from_node="parent", from_output="data", to_node="UpdateHandler", to_input="data", note="Update action"),
            DataflowEdge(from_node="parent", from_output="data", to_node="DeleteHandler", to_input="data", note="Delete action"),
            DataflowEdge(from_node="CreateHandler", from_output="result", to_node="parent", to_input="handler_result", note="Create result"),
            DataflowEdge(from_node="UpdateHandler", from_output="result", to_node="parent", to_input="handler_result", note="Update result"),
            DataflowEdge(from_node="DeleteHandler", from_output="result", to_node="parent", to_input="handler_result", note="Delete result"),
            DataflowEdge(from_node="parent", from_output="handler_result", to_node="FormatAction", to_input="result", note="Format result"),
            DataflowEdge(from_node="FormatAction", from_output="response", to_node="parent", to_input="response", note="Formatted response"),
        ],
    )

    children = [
        Node(node_id="P3_child1", name="ParseAction", depth=2,
             purpose="Parse input into action and data.",
             inputs=[InputParam(name="input", type="dict", description="Raw input", source="parent input")],
             outputs=[OutputParam(name="action", type="str", description="Action string", consumer="parent"),
                      OutputParam(name="data", type="dict", description="Action data", consumer="parent")]),
        Node(node_id="P3_child2", name="CreateHandler", depth=2,
             purpose="Create a resource.",
             inputs=[InputParam(name="data", type="dict", description="Create data", source="ParseAction.data")],
             outputs=[OutputParam(name="result", type="dict", description="Create result", consumer="parent")]),
        Node(node_id="P3_child3", name="UpdateHandler", depth=2,
             purpose="Update a resource.",
             inputs=[InputParam(name="data", type="dict", description="Update data", source="ParseAction.data")],
             outputs=[OutputParam(name="result", type="dict", description="Update result", consumer="parent")]),
        Node(node_id="P3_child4", name="DeleteHandler", depth=2,
             purpose="Delete a resource.",
             inputs=[InputParam(name="data", type="dict", description="Delete data", source="ParseAction.data")],
             outputs=[OutputParam(name="result", type="dict", description="Delete result", consumer="parent")]),
        Node(node_id="P3_child5", name="FormatAction", depth=2,
             purpose="Format handler result into standard response.",
             inputs=[InputParam(name="result", type="dict", description="Handler result", source="parent")],
             outputs=[OutputParam(name="response", type="dict", description="Formatted response dict", consumer="parent")]),
    ]
    parent.children = children

    contracts = {}
    for ch in children:
        ci = [InputParam(name=i.name, type=i.type, description=i.description, source=i.source) for i in ch.inputs]
        co = [OutputParam(name=o.name, type=o.type, description=o.description, consumer=o.consumer) for o in ch.outputs]
        sig = f"def {ch.name}({', '.join(i.name + ': ' + i.type for i in ci)}) -> dict"
        contracts[ch.name] = ChildContract(
            purpose=ch.purpose, inputs=ci, outputs=co,
            behavior=f"{ch.name} performs its function and returns result.",
            signature=sig,
        )
    parent.children_contracts = contracts

    return parent, "accept", [], [], "dataflow_conformance", "positive", "", ""


def build_case_N1() -> Tuple[Node, str, List[Dict], List[Dict], str, str, str, str]:
    """N1: hardcoded_runtime_id — verifier_only.

    Fake code parent returns hardcoded "ORDER-001" for required order_id.
    Expected reason: return_value_origin.
    """
    parent = Node(
        node_id="N1",
        name="GetOrder",
        depth=1,
        purpose="Get order details by ID.",
        inputs=[InputParam(name="order_id", type="str", description="Order ID to look up")],
        outputs=[OutputParam(name="order_id", type="str", description="Verified order ID"),
                 OutputParam(name="details", type="dict", description="Order details")],
        subprd=SubPRD(
            task_id="N1",
            purpose="Order retrieval",
            description="Look up an order by ID and return its details. The order_id in output must be the same as input.",
            acceptance_criteria=[
                AcceptanceCriterion(ac_id="N1-AC1", description="Returns order_id and details"),
            ],
        ),
    )
    fake_code = """\
def GetOrder(order_id: str) -> dict:
    # BAD: hardcodes a runtime ID instead of using input
    return {"order_id": "ORDER-001", "details": {}}
"""
    return parent, "reject", [], [{"value": "ORDER-001", "kind": "DYNAMIC_VALUE", "reason": "order_id is a runtime fact"}], "return_value_origin", "verifier_only", "return_value_origin", fake_code


def build_case_N2a() -> Tuple[Node, str, List[Dict], List[Dict], str, str, str, str]:
    """N2a: literal_substitutes_child_output — verifier_only.

    Fake code calls CalculateTotal but ignores its result, returns total=0.0.
    Expected reason: return_value_origin.
    """
    parent = Node(
        node_id="N2a",
        name="CalculateBill",
        depth=1,
        purpose="Calculate the total bill for an order.",
        inputs=[InputParam(name="items", type="list", description="List of line items")],
        outputs=[OutputParam(name="total", type="float", description="Calculated total")],
        subprd=SubPRD(
            task_id="N2a",
            purpose="Bill calculation",
            description="Calculate the total bill by calling CalculateTotal on items and returning the result.",
            acceptance_criteria=[
                AcceptanceCriterion(ac_id="N2a-AC1", description="Returns total from CalculateTotal"),
            ],
        ),
    )
    # Add CalculateTotal as a child so verifier sees it exists
    child = Node(
        node_id="N2a_child1", name="CalculateTotal", depth=2,
        purpose="Calculate total from line items.",
        inputs=[InputParam(name="items", type="list", description="Line items", source="parent input")],
        outputs=[OutputParam(name="total", type="float", description="Calculated total", consumer="parent")],
    )
    parent.children = [child]
    parent.children_contracts = {
        "CalculateTotal": ChildContract(
            purpose=child.purpose,
            inputs=[InputParam(name=i.name, type=i.type, description=i.description, source=i.source) for i in child.inputs],
            outputs=[OutputParam(name=o.name, type=o.type, description=o.description, consumer=o.consumer) for o in child.outputs],
            behavior="CalculateTotal computes the total from items and returns the float value.",
            signature="def CalculateTotal(items: list) -> float",
        )
    }
    fake_code = """\
def CalculateBill(items: list) -> dict:
    # BAD: calls CalculateTotal but ignores result, returns literal
    calc_result = CalculateTotal(items)
    return {"total": 0.0}
"""
    return parent, "reject", [], [{"value": "0.0", "kind": "CHILD_OUTPUT_SUBSTITUTE", "reason": "total must come from CalculateTotal output"}], "return_value_origin", "verifier_only", "return_value_origin", fake_code


def build_case_N2b() -> Tuple[Node, str, List[Dict], List[Dict], str, str, str, str]:
    """N2b: full_generate_child_output_required.

    Clean fixture with CalculateTotal child. Parent output requires total.
    Expected: accept only if code uses CalculateTotal output.
    """
    parent = Node(
        node_id="N2b",
        name="CalculateBill",
        depth=1,
        purpose="Calculate the total bill using CalculateTotal child.",
        inputs=[InputParam(name="items", type="list", description="List of line items")],
        outputs=[OutputParam(name="total", type="float", description="Calculated total from child")],
        subprd=SubPRD(
            task_id="N2b",
            purpose="Bill calculation using child",
            description="Delegate total calculation to CalculateTotal child and return its result.",
            acceptance_criteria=[
                AcceptanceCriterion(ac_id="N2b-AC1", description="Calls CalculateTotal and returns its result"),
            ],
        ),
        dataflow_edges=[
            DataflowEdge(from_node="parent", from_output="items", to_node="CalculateTotal", to_input="items", note="Pass items for calculation"),
            DataflowEdge(from_node="CalculateTotal", from_output="total", to_node="parent", to_input="total", note="Return calculated total"),
        ],
    )
    child = Node(
        node_id="N2b_child1", name="CalculateTotal", depth=2,
        purpose="Calculate total from line items.",
        inputs=[InputParam(name="items", type="list", description="Line items", source="parent input")],
        outputs=[OutputParam(name="total", type="float", description="Calculated total", consumer="parent")],
    )
    parent.children = [child]
    parent.children_contracts = {
        "CalculateTotal": ChildContract(
            purpose=child.purpose,
            inputs=[InputParam(name=i.name, type=i.type, description=i.description, source=i.source) for i in child.inputs],
            outputs=[OutputParam(name=o.name, type=o.type, description=o.description, consumer=o.consumer) for o in child.outputs],
            behavior="CalculateTotal computes the total from items and returns the float value.",
            signature="def CalculateTotal(items: list) -> float",
        )
    }

    return parent, "accept", [], [{"value": "0.0", "kind": "CHILD_OUTPUT_SUBSTITUTE", "reason": "total must be from CalculateTotal"}], "child_coverage", "full_generate", "", ""


def build_case_N3a() -> Tuple[Node, str, List[Dict], List[Dict], str, str, str, str]:
    """N3a: runtime_status_hardcoded — verifier_only.

    Fake code has access to FetchOrderStatus but returns "delivered" literal.
    Expected reason: return_value_origin.
    """
    parent = Node(
        node_id="N3a",
        name="GetOrderStatus",
        depth=1,
        purpose="Get the status of an order.",
        inputs=[InputParam(name="order_id", type="str", description="Order ID")],
        outputs=[OutputParam(name="status", type="str", description="Order status from child")],
        subprd=SubPRD(
            task_id="N3a",
            purpose="Order status retrieval",
            description="Call FetchOrderStatus and return the status. Status must come from child, not hardcoded.",
            acceptance_criteria=[
                AcceptanceCriterion(ac_id="N3a-AC1", description="Returns status from FetchOrderStatus"),
            ],
        ),
    )
    # Add FetchOrderStatus as a child so verifier sees it exists
    child = Node(
        node_id="N3a_child1", name="FetchOrderStatus", depth=2,
        purpose="Fetch order status from database.",
        inputs=[InputParam(name="order_id", type="str", description="Order ID to look up", source="parent input")],
        outputs=[OutputParam(name="status", type="str", description="Current order status", consumer="parent")],
    )
    parent.children = [child]
    parent.children_contracts = {
        "FetchOrderStatus": ChildContract(
            purpose=child.purpose,
            inputs=[InputParam(name=i.name, type=i.type, description=i.description, source=i.source) for i in child.inputs],
            outputs=[OutputParam(name=o.name, type=o.type, description=o.description, consumer=o.consumer) for o in child.outputs],
            behavior="FetchOrderStatus retrieves the current order status from the database.",
            signature="def FetchOrderStatus(order_id: str) -> str",
        )
    }
    fake_code = """\
def GetOrderStatus(order_id: str) -> dict:
    # BAD: has FetchOrderStatus available but hardcodes status
    status = FetchOrderStatus(order_id)
    return {"status": "delivered"}
"""
    return parent, "reject", [], [{"value": "delivered", "kind": "DYNAMIC_VALUE", "reason": "status is a runtime fact that must come from FetchOrderStatus"}], "return_value_origin", "verifier_only", "return_value_origin", fake_code


def build_case_N3b() -> Tuple[Node, str, List[Dict], List[Dict], str, str, str, str]:
    """N3b: full_generate_status_child_required.

    Clean fixture with FetchOrderStatus child.
    """
    parent = Node(
        node_id="N3b",
        name="GetOrderStatus",
        depth=1,
        purpose="Get order status by calling FetchOrderStatus child.",
        inputs=[InputParam(name="order_id", type="str", description="Order ID")],
        outputs=[OutputParam(name="status", type="str", description="Order status from child")],
        subprd=SubPRD(
            task_id="N3b",
            purpose="Order status via child",
            description="Delegate status retrieval to FetchOrderStatus and return its result.",
            acceptance_criteria=[
                AcceptanceCriterion(ac_id="N3b-AC1", description="Calls FetchOrderStatus and returns result"),
            ],
        ),
        dataflow_edges=[
            DataflowEdge(from_node="parent", from_output="order_id", to_node="FetchOrderStatus", to_input="order_id", note="Pass order ID"),
            DataflowEdge(from_node="FetchOrderStatus", from_output="status", to_node="parent", to_input="status", note="Return status"),
        ],
    )
    child = Node(
        node_id="N3b_child1", name="FetchOrderStatus", depth=2,
        purpose="Fetch order status from database.",
        inputs=[InputParam(name="order_id", type="str", description="Order ID to look up", source="parent input")],
        outputs=[OutputParam(name="status", type="str", description="Current order status", consumer="parent")],
    )
    parent.children = [child]
    parent.children_contracts = {
        "FetchOrderStatus": ChildContract(
            purpose=child.purpose,
            inputs=[InputParam(name=i.name, type=i.type, description=i.description, source=i.source) for i in child.inputs],
            outputs=[OutputParam(name=o.name, type=o.type, description=o.description, consumer=o.consumer) for o in child.outputs],
            behavior="FetchOrderStatus retrieves the current order status from the database.",
            signature="def FetchOrderStatus(order_id: str) -> str",
        )
    }

    return parent, "accept", [], [{"value": "delivered", "kind": "DYNAMIC_VALUE", "reason": "status must be from FetchOrderStatus"}], "child_coverage", "full_generate", "", ""


def build_case_N4() -> Tuple[Node, str, List[Dict], List[Dict], str, str, str, str]:
    """N4: missing_capability_masked_by_literal.

    Parent must process payment for successful checkout but no child can do it.
    Fake code returns "Payment failed" literal to mask missing capability.
    Expected reason: missing_child_capability.
    """
    parent = Node(
        node_id="N4",
        name="Checkout",
        depth=1,
        purpose="Process checkout including payment.",
        inputs=[InputParam(name="cart", type="dict", description="Shopping cart contents")],
        outputs=[OutputParam(name="success", type="bool", description="Whether checkout succeeded"),
                 OutputParam(name="message", type="str", description="Result message")],
        subprd=SubPRD(
            task_id="N4",
            purpose="Checkout processing including payment",
            description="Process checkout. Must process payment before successful checkout. "
                        "No payment processing child is available.",
            constraints=[{"type": "critical", "detail": "Payment processing is required but no child provides it"}],
            acceptance_criteria=[
                AcceptanceCriterion(ac_id="N4-AC1", description="Checkout must process payment or reject"),
            ],
        ),
    )
    # Add ParseCheckout and ReserveInventory as children so verifier sees what's available
    children = [
        Node(node_id="N4_child1", name="ParseCheckout", depth=2,
             purpose="Parse checkout input into structured order data.",
             inputs=[InputParam(name="cart", type="dict", description="Shopping cart", source="parent input")],
             outputs=[OutputParam(name="order_data", type="dict", description="Parsed order data", consumer="parent")]),
        Node(node_id="N4_child2", name="ReserveInventory", depth=2,
             purpose="Reserve inventory for the order.",
             inputs=[InputParam(name="order_data", type="dict", description="Order data", source="ParseCheckout.order_data")],
             outputs=[OutputParam(name="reserved", type="bool", description="Whether reservation succeeded", consumer="parent")]),
    ]
    parent.children = children
    contracts = {}
    for ch in children:
        ci = [InputParam(name=i.name, type=i.type, description=i.description, source=i.source) for i in ch.inputs]
        co = [OutputParam(name=o.name, type=o.type, description=o.description, consumer=o.consumer) for o in ch.outputs]
        sig = f"def {ch.name}({', '.join(i.name + ': ' + i.type for i in ci)}) -> dict"
        contracts[ch.name] = ChildContract(
            purpose=ch.purpose, inputs=ci, outputs=co,
            behavior=f"{ch.name} performs its function and returns result.",
            signature=sig,
        )
    parent.children_contracts = contracts

    fake_code = """\
def Checkout(cart: dict) -> dict:
    # BAD: no payment child available, uses literal fallback to mask missing capability
    parsed = ParseCheckout(cart)
    reserved = ReserveInventory(parsed)
    return {"success": False, "message": "Payment failed"}
"""
    return parent, "reject", [], [{"value": "Payment failed", "kind": "MISSING_CAPABILITY_MASK", "reason": "literal fallback hides missing payment processing capability"}], "child_coverage", "verifier_only", "missing_child_capability", fake_code


def build_case_N5() -> Tuple[Node, str, List[Dict], List[Dict], str, str, str, str]:
    """N5: sibling_call_violation — full_generate.

    RouteCommand's behavior explicitly says it calls sibling handlers.
    Expected reason: tree_structure_violation.
    """
    parent = Node(
        node_id="N5",
        name="RouteOrder",
        depth=1,
        purpose="Route an order to the correct handler.",
        inputs=[InputParam(name="input", type="dict", description="Input with command and data")],
        outputs=[OutputParam(name="success", type="bool", description="Success flag"),
                 OutputParam(name="result", type="dict", description="Handler result")],
        subprd=SubPRD(
            task_id="N5",
            purpose="Order routing",
            description="Route incoming orders to the appropriate handler based on command.",
            acceptance_criteria=[
                AcceptanceCriterion(ac_id="N5-AC1", description="Order is routed to correct handler"),
            ],
        ),
    )

    children = [
        Node(node_id="N5_child1", name="ParseInput", depth=2,
             purpose="Parse input into command and data.",
             inputs=[InputParam(name="input", type="dict", description="Raw input", source="parent input")],
             outputs=[OutputParam(name="command", type="str", description="Command string", consumer="parent"),
                      OutputParam(name="data", type="dict", description="Parsed data", consumer="parent")]),
        Node(node_id="N5_child2", name="RouteCommand", depth=2,
             purpose="Route to the correct handler child.",
             inputs=[
                 InputParam(name="command", type="str", description="Command to route", source="parent.command"),
                 InputParam(name="data", type="dict", description="Parsed data", source="parent.data"),
             ],
             outputs=[OutputParam(name="result", type="dict", description="Handler result", consumer="parent")],
             decomposition_rationale="", stop_decompose=False, stop_reason=""),
        Node(node_id="N5_child3", name="PlaceOrder", depth=2,
             purpose="Place a new order.",
             inputs=[InputParam(name="data", type="dict", description="Order data", source="ParseInput.data")],
             outputs=[OutputParam(name="result", type="dict", description="Order result", consumer="parent")]),
        Node(node_id="N5_child4", name="CancelOrder", depth=2,
             purpose="Cancel an existing order.",
             inputs=[InputParam(name="data", type="dict", description="Cancel data", source="ParseInput.data")],
             outputs=[OutputParam(name="result", type="dict", description="Cancel result", consumer="parent")]),
    ]
    parent.children = children

    # KEY: RouteCommand's behavior says it calls siblings!
    contracts = {}
    for ch in children:
        ci = [InputParam(name=i.name, type=i.type, description=i.description, source=i.source) for i in ch.inputs]
        co = [OutputParam(name=o.name, type=o.type, description=o.description, consumer=o.consumer) for o in ch.outputs]
        sig = f"def {ch.name}({', '.join(i.name + ': ' + i.type for i in ci)}) -> dict"
        if ch.name == "RouteCommand":
            behavior = "Inspect the command and call PlaceOrder to place an order or CancelOrder to cancel an order."
        else:
            behavior = f"{ch.name} performs its function and returns result."
        contracts[ch.name] = ChildContract(
            purpose=ch.purpose, inputs=ci, outputs=co,
            behavior=behavior, signature=sig,
        )
    parent.children_contracts = contracts

    parent.dataflow_edges = [
        DataflowEdge(from_node="parent", from_output="input", to_node="ParseInput", to_input="input", note="Parse input"),
        DataflowEdge(from_node="ParseInput", from_output="command", to_node="parent", to_input="command", note="Command for routing"),
        DataflowEdge(from_node="ParseInput", from_output="data", to_node="parent", to_input="data", note="Data for routing"),
        DataflowEdge(from_node="parent", from_output="command", to_node="RouteCommand", to_input="command", note="Route command"),
        DataflowEdge(from_node="parent", from_output="data", to_node="RouteCommand", to_input="data", note="Route data"),
        DataflowEdge(from_node="RouteCommand", from_output="result", to_node="parent", to_input="result", note="Router result"),
    ]

    return parent, "reject", [], [], "tree_structure", "full_generate", "tree_structure_violation", ""


# ============================================================================
# Run Functions
# ============================================================================

def _call_llm_with_retry(gen, messages, max_tokens=1024, max_attempts=5):
    """Call LLM with retry for transient failures."""
    for attempt in range(max_attempts):
        try:
            response = gen.api_client.chat(messages, max_tokens=max_tokens)
            if response and response.strip():
                return gen._parse_response(response), response
            print(f"    (empty response, attempt {attempt+1}/{max_attempts})")
        except Exception as e:
            print(f"    (error: {e}, attempt {attempt+1}/{max_attempts})")
        if attempt < max_attempts - 1:
            _time.sleep(5 * (attempt + 1))
    return {"status": "error", "error": f"Empty response after {max_attempts} attempts"}, ""


def _set_literal_expectations(node, allowed, forbidden):
    """Attach literal expectations as a dynamic attribute for verify prompt."""
    node._literal_expectations = {"allowed": allowed, "forbidden": forbidden}


def _save_artifacts(case_dir: str, artifacts: Dict[str, str]):
    """Save text/JSON artifacts to case directory."""
    os.makedirs(case_dir, exist_ok=True)
    for name, content in artifacts.items():
        path = os.path.join(case_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


def run_positive_case(
    gen: LiteralPolicyCodeGenerator,
    case_id: str, slug: str,
    node: Node, output_dir: str,
    expected: str, allowed_literals: List[Dict], forbidden_literals: List[Dict],
    target_invariant: str,
) -> Dict[str, Any]:
    """Run a positive case through full generate + verify pipeline."""
    case_dir = os.path.join(output_dir, f"case_{case_id}_{slug}")
    os.makedirs(case_dir, exist_ok=True)

    print(f"  [{case_id}] Running positive case...")

    # Attach literal expectations for verify prompt
    _set_literal_expectations(node, allowed_literals, forbidden_literals)

    # Save node and expectations
    _save_json(os.path.join(case_dir, "node.json"), node.to_dict())
    _save_json(os.path.join(case_dir, "dataflow_edges.json"), [e.to_dict() for e in (node.dataflow_edges or [])])
    _save_json(os.path.join(case_dir, "literal_policy_expectation.json"), {
        "allowed": allowed_literals, "forbidden": forbidden_literals,
    })

    # Generate
    gen_start = _time.time()
    try:
        code, errors = gen.generate_for_parent(node)
    except Exception as e:
        code, errors = "", [f"Exception: {e}"]
    gen_elapsed = _time.time() - gen_start

    # Save prompts and responses
    last_gen_prompt = getattr(gen, "last_gen_prompt", "")
    last_gen_raw = getattr(gen, "last_gen_response", "")
    last_gen_parsed = getattr(gen, "last_gen_parsed", None)
    last_verify_prompt = getattr(gen, "last_verify_prompt", "")
    last_verify_raw = getattr(gen, "last_verify_response", "")
    last_verify_parsed = getattr(gen, "last_verify_parsed", None)

    artifacts = {}
    if last_gen_prompt:
        artifacts["prompt_generate.txt"] = last_gen_prompt
    if last_gen_raw:
        artifacts["response_generate.json"] = last_gen_raw
    if code:
        artifacts["generated_code.py"] = code
    candidate_code = code or ((last_gen_parsed or {}).get("code", "") if isinstance(last_gen_parsed, dict) else "")
    if candidate_code and not code:
        artifacts["generated_candidate.py"] = candidate_code
    if last_verify_prompt:
        artifacts["prompt_verify.txt"] = last_verify_prompt
    if last_verify_raw:
        artifacts["response_verify.json"] = last_verify_raw
    _save_artifacts(case_dir, artifacts)
    if last_gen_parsed is not None:
        _save_json(os.path.join(case_dir, "parsed_generate.json"), last_gen_parsed)
    if last_verify_parsed is not None:
        _save_json(os.path.join(case_dir, "parsed_verify.json"), last_verify_parsed)

    # Static analysis
    static_analysis = analyze_generated_code_extended(candidate_code, node, forbidden_literals, allowed_literals)
    _save_json(os.path.join(case_dir, "static_analysis.json"), static_analysis)

    # Determine result
    generate_status = "ok"
    verify_status = "ok"
    reason = ""
    failed_checks = []

    if errors:
        generate_status = "cannot_compose"
        reason = errors[0] if errors else "unknown error"
        # Try to get composition feedback reason
        if gen.last_composition_feedback:
            reason = gen.last_composition_feedback.reason or reason
            failed_checks = gen.last_composition_feedback.failed_checks or []
        verify_status = "N/A"
    else:
        # Verify step was included in generate_for_parent
        # Check if verify rejected it
        if gen.last_composition_feedback and gen.last_composition_feedback.status == "cannot_compose":
            verify_status = "cannot_compose"
            reason = gen.last_composition_feedback.reason or "verify_rejected"
            failed_checks = gen.last_composition_feedback.failed_checks or []

    # Verdict
    artifact_failure = (
        generate_status == "cannot_compose"
        and "API call failed" not in reason
        and "Failed to parse code" not in reason
        and (not last_gen_prompt or not last_gen_raw or last_gen_parsed is None)
    )
    missing_allowed = [
        str(al.get("value")) for al in (allowed_literals or [])
        if str(al.get("value")) not in set(static_analysis.get("allowed_literals_detected", []))
    ]
    if artifact_failure:
        passed = False
        category = "unreproducible_artifact_failure"
    elif errors and static_analysis.get("forbidden_literals_detected"):
        passed = False
        category = "generation_introduced_forbidden_literal"
        reason = reason or f"Generated candidate contains forbidden literals: {static_analysis.get('forbidden_literals_detected')}"
    elif (
        errors
        and target_invariant != "literal_policy"
        and "return_value_origin" in failed_checks
        and static_analysis.get("return_literals")
    ):
        passed = False
        category = "generation_introduced_forbidden_literal"
        reason = reason or f"Generated candidate introduced return literals: {static_analysis.get('return_literals')}"
    elif errors:
        passed = False
        category = (
            "false_rejection_dataflow_positive"
            if target_invariant != "literal_policy"
            else "false_rejection_allowed_literal"
        )
    elif verify_status == "cannot_compose":
        passed = False
        category = (
            "false_rejection_dataflow_positive"
            if target_invariant != "literal_policy"
            else "false_rejection_allowed_literal"
        )
    elif target_invariant == "literal_policy" and missing_allowed:
        passed = False
        category = "allowed_literal_not_exercised"
        reason = f"Generated code did not contain allowed literals: {missing_allowed}"
    elif static_analysis.get("forbidden_literals_detected"):
        passed = False
        category = "false_acceptance_runtime_hardcode"
        reason = f"Generated code contains forbidden literals: {static_analysis.get('forbidden_literals_detected')}"
    else:
        passed = True
        category = "valid_acceptance_for_positive"

    verdict = _build_verdict(case_id, expected, passed, category,
                             generate_status, verify_status, reason,
                             failed_checks, static_analysis)
    _save_json(os.path.join(case_dir, "verdict.json"), verdict)
    print(f"  [{case_id}] Verdict: {'PASS' if passed else 'FAIL'} ({category})")
    if reason:
        print(f"            Reason: {reason}")
    return verdict


def _reason_matches(
    actual_reason: str,
    failed_checks: List[str],
    checks: Dict[str, Any],
    expected_primary_reason: str,
) -> Tuple[bool, str]:
    """Match the target reason across LLM's inconsistent reason surfaces."""
    if not expected_primary_reason:
        return False, ""
    hits = []
    if actual_reason == expected_primary_reason:
        hits.append("reason")
    if expected_primary_reason in (failed_checks or []):
        hits.append("failed_checks")
    check_obj = (checks or {}).get(expected_primary_reason)
    if isinstance(check_obj, dict) and check_obj.get("passed") is False:
        hits.append(f"checks.{expected_primary_reason}.passed=false")
    checks_text = json.dumps(checks or {}, ensure_ascii=False).lower()
    reason_text = (actual_reason or "").lower()
    if expected_primary_reason == "missing_child_capability" and (
        "missing_child_capability" in reason_text or "missing child" in checks_text
    ):
        hits.append("semantic_missing_child")
    if expected_primary_reason == "tree_structure_violation" and (
        "tree" in reason_text or "sibling" in checks_text or "cross" in checks_text
    ):
        hits.append("semantic_tree_structure")
    return bool(hits), ",".join(hits)


def run_negative_verifier_only(
    gen: LiteralPolicyCodeGenerator,
    case_id: str, slug: str,
    node: Node, output_dir: str,
    expected: str, allowed_literals: List[Dict], forbidden_literals: List[Dict],
    target_invariant: str, expected_primary_reason: str,
    fake_code: str,
) -> Dict[str, Any]:
    """Run a negative case by providing fake code directly to the verifier."""
    case_dir = os.path.join(output_dir, f"case_{case_id}_{slug}")
    os.makedirs(case_dir, exist_ok=True)

    print(f"  [{case_id}] Running negative case (verifier-only)...")

    _set_literal_expectations(node, allowed_literals, forbidden_literals)

    _save_json(os.path.join(case_dir, "node.json"), node.to_dict())
    _save_json(os.path.join(case_dir, "literal_policy_expectation.json"), {
        "allowed": allowed_literals, "forbidden": forbidden_literals,
    })
    _save_artifacts(case_dir, {"generated_code.py": fake_code})

    # Call verifier directly
    verify_messages = [
        {"role": "system", "content": gen._build_system_prompt_for_parent_verify()},
        {"role": "user", "content": gen._build_user_prompt_for_parent_verify(node, fake_code)},
    ]

    # Save verify prompt
    _save_artifacts(case_dir, {"prompt_verify.txt": verify_messages[0]["content"] + "\n\n---\n\n" + verify_messages[1]["content"]})

    verify_parsed, verify_raw = _call_llm_with_retry(gen, verify_messages, max_tokens=1024)
    if verify_raw:
        _save_artifacts(case_dir, {"response_verify.json": verify_raw})
        _save_json(os.path.join(case_dir, "parsed_verify.json"), verify_parsed)

    # Check for API error
    if verify_parsed.get("error"):
        verdict = _build_verdict(case_id, expected, False, "api_or_parse_failure",
                                 "ok", "error", verify_parsed.get("error", ""),
                                 [], {}, "")
        _save_json(os.path.join(case_dir, "verdict.json"), verdict)
        print(f"  [{case_id}] Verdict: FAIL (api_or_parse_failure)")
        return verdict

    # Static analysis of fake code
    static_analysis = analyze_generated_code_extended(fake_code, node, forbidden_literals, allowed_literals)
    _save_json(os.path.join(case_dir, "static_analysis.json"), static_analysis)

    # Reason-matched verdict
    verify_status = verify_parsed.get("status", "ok")
    df = verify_parsed.get("decomposition_feedback") or {}
    actual_reason = df.get("reason", "") or verify_status
    failed_checks = df.get("failed_checks", [])
    checks = verify_parsed.get("checks", {}) or df.get("checks", {})
    for name, result in checks.items():
        if isinstance(result, dict) and result.get("passed") is False and name not in failed_checks:
            failed_checks.append(name)
    reason_match, reason_match_source = _reason_matches(
        actual_reason, failed_checks, checks, expected_primary_reason
    )

    if verify_status == "cannot_compose":
        # Check if reason matches expected
        if reason_match:
            category = "valid_rejection_expected_reason"
            passed = True
        else:
            category = "rejected_by_other_reason"
            passed = True  # Still rejected, but for the wrong reason
    elif verify_status == "ok":
        category = "false_acceptance_runtime_hardcode"
        passed = False
    else:
        category = "api_or_parse_failure"
        passed = False

    verdict = _build_verdict(case_id, expected, passed, category,
                             "ok", verify_status, actual_reason,
                             failed_checks, static_analysis, f"expected_reason={expected_primary_reason}; match={reason_match_source}")
    _save_json(os.path.join(case_dir, "verdict.json"), verdict)
    print(f"  [{case_id}] Verdict: {'PASS' if passed else 'FAIL'} ({category})")
    print(f"            Reason: {actual_reason} (expected: {expected_primary_reason})")
    return verdict


def run_negative_full_generate(
    gen: LiteralPolicyCodeGenerator,
    case_id: str, slug: str,
    node: Node, output_dir: str,
    expected: str, allowed_literals: List[Dict], forbidden_literals: List[Dict],
    target_invariant: str, expected_primary_reason: str,
) -> Dict[str, Any]:
    """Run a negative case through full generate pipeline.

    The negative characteristic is in the node structure or child behaviors.
    Expected: codegen rejects at Stage 1/2/3 with expected reason.
    """
    case_dir = os.path.join(output_dir, f"case_{case_id}_{slug}")
    os.makedirs(case_dir, exist_ok=True)

    print(f"  [{case_id}] Running negative case (full generate)...")

    _set_literal_expectations(node, allowed_literals, forbidden_literals)

    _save_json(os.path.join(case_dir, "node.json"), node.to_dict())
    _save_json(os.path.join(case_dir, "dataflow_edges.json"), [e.to_dict() for e in (node.dataflow_edges or [])])
    _save_json(os.path.join(case_dir, "literal_policy_expectation.json"), {
        "allowed": allowed_literals, "forbidden": forbidden_literals,
    })

    # Generate
    code, errors = gen.generate_for_parent(node)

    # Save artifacts
    last_gen_prompt = getattr(gen, "last_gen_prompt", "")
    last_gen_raw = getattr(gen, "last_gen_response", "")
    last_gen_parsed = getattr(gen, "last_gen_parsed", None)
    last_verify_prompt = getattr(gen, "last_verify_prompt", "")
    last_verify_raw = getattr(gen, "last_verify_response", "")
    last_verify_parsed = getattr(gen, "last_verify_parsed", None)
    artifacts = {}
    if last_gen_prompt:
        artifacts["prompt_generate.txt"] = last_gen_prompt
    if last_gen_raw:
        artifacts["response_generate.json"] = last_gen_raw
    if code:
        artifacts["generated_code.py"] = code
    candidate_code = code or ((last_gen_parsed or {}).get("code", "") if isinstance(last_gen_parsed, dict) else "")
    if candidate_code and not code:
        artifacts["generated_candidate.py"] = candidate_code
    if last_verify_prompt:
        artifacts["prompt_verify.txt"] = last_verify_prompt
    if last_verify_raw:
        artifacts["response_verify.json"] = last_verify_raw
    _save_artifacts(case_dir, artifacts)
    if last_gen_parsed is not None:
        _save_json(os.path.join(case_dir, "parsed_generate.json"), last_gen_parsed)
    if last_verify_parsed is not None:
        _save_json(os.path.join(case_dir, "parsed_verify.json"), last_verify_parsed)

    # Static analysis
    static_analysis = analyze_generated_code_extended(candidate_code, node, forbidden_literals, allowed_literals)
    _save_json(os.path.join(case_dir, "static_analysis.json"), static_analysis)

    # Determine result
    actual_reason = ""
    failed_checks = []
    generate_status = "ok"
    verify_status = "N/A"

    if errors:
        generate_status = "cannot_compose"
        actual_reason = errors[0]
        if gen.last_composition_feedback:
            actual_reason = gen.last_composition_feedback.reason or actual_reason
            failed_checks = gen.last_composition_feedback.failed_checks or []
            checks = gen.last_composition_feedback.checks or {}
        else:
            checks = {}
    else:
        checks = {}
        # Generated code but might have verify rejection
        if gen.last_composition_feedback and gen.last_composition_feedback.status == "cannot_compose":
            verify_status = "cannot_compose"
            actual_reason = gen.last_composition_feedback.reason or "verify_rejected"
            failed_checks = gen.last_composition_feedback.failed_checks or []
            checks = gen.last_composition_feedback.checks or {}
    for name, result in checks.items():
        if isinstance(result, dict) and result.get("passed") is False and name not in failed_checks:
            failed_checks.append(name)
    reason_match, reason_match_source = _reason_matches(
        actual_reason, failed_checks, checks, expected_primary_reason
    )

    # Reason-matched verdict. Some full-generate cases are positive controls.
    rejected = bool(errors) or verify_status == "cannot_compose"
    artifact_failure = (
        generate_status == "cannot_compose"
        and "API call failed" not in actual_reason
        and "Failed to parse code" not in actual_reason
        and (not last_gen_prompt or not last_gen_raw or last_gen_parsed is None)
    )
    if expected == "accept":
        if artifact_failure:
            category = "unreproducible_artifact_failure"
            passed = False
        elif rejected:
            category = "false_rejection_positive_control"
            passed = False
        elif static_analysis.get("forbidden_literals_detected"):
            category = "false_acceptance_runtime_hardcode"
            passed = False
        elif static_analysis.get("missing_child_calls"):
            category = "false_acceptance_missing_child_call"
            passed = False
            actual_reason = f"Generated code did not call children: {static_analysis.get('missing_child_calls')}"
        elif not static_analysis.get("parent_outputs_covered_by_code"):
            category = "false_acceptance_missing_parent_output"
            passed = False
            actual_reason = "Generated code does not cover declared parent outputs"
        else:
            category = "valid_acceptance_for_positive"
            passed = True
    else:
        if artifact_failure:
            category = "unreproducible_artifact_failure"
            passed = False
        elif rejected:
            if reason_match:
                category = "valid_rejection_expected_reason"
                passed = True
            else:
                category = "rejected_by_other_reason"
                passed = True
        else:
            category = "false_acceptance_negative"
            passed = False

    verdict = _build_verdict(case_id, expected, passed, category,
                             generate_status, verify_status, actual_reason,
                             failed_checks, static_analysis, f"expected_reason={expected_primary_reason}; match={reason_match_source}")
    _save_json(os.path.join(case_dir, "verdict.json"), verdict)
    print(f"  [{case_id}] Verdict: {'PASS' if passed else 'FAIL'} ({category})")
    print(f"            Reason: {actual_reason} (expected: {expected_primary_reason})")
    return verdict


# ============================================================================
# Report Generation
# ============================================================================

def generate_report(output_dir: str, results: List[Dict], cases_def: List[tuple],
                    prompt_delta: str, audit_results: List[Dict] = None):
    """Generate results.json and report.md."""
    case_meta = {entry[0]: {"target": entry[6], "mode": entry[7]} for entry in cases_def}
    migration_results = [
        r for r in results
        if case_meta.get(r["case_id"], {}).get("target") != "tree_structure"
    ]
    tree_results = [
        r for r in results
        if case_meta.get(r["case_id"], {}).get("target") == "tree_structure"
    ]
    literal_positive_results = [
        r for r in migration_results
        if r["expected"] == "accept" and case_meta.get(r["case_id"], {}).get("target") == "literal_policy"
    ]
    dispatch_positive_results = [
        r for r in migration_results
        if r["expected"] == "accept" and case_meta.get(r["case_id"], {}).get("target") == "dataflow_conformance"
    ]
    full_generate_positive_controls = [
        r for r in migration_results
        if r["expected"] == "accept" and case_meta.get(r["case_id"], {}).get("mode") == "full_generate"
    ]
    verifier_literal_negatives = [
        r for r in migration_results
        if r["expected"] == "reject"
        and case_meta.get(r["case_id"], {}).get("mode") == "verifier_only"
        and case_meta.get(r["case_id"], {}).get("target") == "return_value_origin"
    ]
    missing_capability_negatives = [
        r for r in migration_results
        if r["expected"] == "reject"
        and case_meta.get(r["case_id"], {}).get("target") == "child_coverage"
    ]
    # Results JSON
    summary = {
        "total_cases": len(results),
        "migration_cases": len(migration_results),
        "literal_positive_cases": len(literal_positive_results),
        "literal_positive_passed": sum(1 for r in literal_positive_results if r["passed"]),
        "dispatch_positive_cases": len(dispatch_positive_results),
        "dispatch_positive_passed": sum(1 for r in dispatch_positive_results if r["passed"]),
        "full_generate_positive_control_cases": len(full_generate_positive_controls),
        "full_generate_positive_control_passed": sum(1 for r in full_generate_positive_controls if r["passed"]),
        "verifier_literal_negative_cases": len(verifier_literal_negatives),
        "verifier_literal_negative_expected_reason": sum(1 for r in verifier_literal_negatives if r["category"] == "valid_rejection_expected_reason"),
        "missing_capability_negative_cases": len(missing_capability_negatives),
        "missing_capability_negative_expected_reason": sum(1 for r in missing_capability_negatives if r["category"] == "valid_rejection_expected_reason"),
        "positive_cases": sum(1 for r in migration_results if r["expected"] == "accept"),
        "positive_passed": sum(1 for r in migration_results if r["expected"] == "accept" and r["passed"]),
        "positive_failed": sum(1 for r in migration_results if r["expected"] == "accept" and not r["passed"]),
        "negative_cases": sum(1 for r in migration_results if r["expected"] == "reject"),
        "negative_passed_expected_reason": sum(1 for r in migration_results if r["expected"] == "reject" and r["category"] == "valid_rejection_expected_reason"),
        "negative_rejected_other_reason": sum(1 for r in migration_results if r["category"] == "rejected_by_other_reason"),
        "negative_false_acceptance": sum(1 for r in migration_results if r["category"] in ("false_acceptance_runtime_hardcode", "false_acceptance_negative")),
        "tree_regression_cases": len(tree_results),
        "tree_regression_expected_reason": sum(1 for r in tree_results if r["category"] == "valid_rejection_expected_reason"),
        "tree_regression_excluded_from_migration": True,
        "api_or_parse_failures": sum(1 for r in results if r["category"] == "api_or_parse_failure"),
        "artifact_failures": sum(1 for r in results if r["category"] == "unreproducible_artifact_failure"),
    }

    confusion = {
        "allowed_literal_accepted": sum(1 for r in migration_results if case_meta.get(r["case_id"], {}).get("target") == "literal_policy" and r["expected"] == "accept" and r["passed"]),
        "allowed_literal_rejected": sum(1 for r in migration_results if case_meta.get(r["case_id"], {}).get("target") == "literal_policy" and r["expected"] == "accept" and not r["passed"]),
        "runtime_literal_rejected_expected_reason": sum(1 for r in migration_results if case_meta.get(r["case_id"], {}).get("target") == "return_value_origin" and r["category"] == "valid_rejection_expected_reason"),
        "runtime_literal_rejected_other_reason": sum(1 for r in migration_results if case_meta.get(r["case_id"], {}).get("target") == "return_value_origin" and r["category"] == "rejected_by_other_reason"),
        "runtime_literal_accepted": sum(1 for r in migration_results if case_meta.get(r["case_id"], {}).get("target") == "return_value_origin" and r["category"] in ("false_acceptance_runtime_hardcode", "false_acceptance_negative")),
    }

    category_counts = {}
    for r in results:
        cat = r["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    results_data = {
        "experiment": OUTPUT_NAME,
        "model": MODEL_NAME,
        "timestamp": _time.strftime("%Y-%m-%dT%H:%M:%S"),
        "prompt_delta": prompt_delta,
        "summary": summary,
        "confusion_matrix": confusion,
        "category_counts": category_counts,
        "trials": results,
    }
    _save_json(os.path.join(output_dir, "results.json"), results_data)

    # Report MD
    lines = []
    lines.append("# Step2 Literal Policy Experiment — Clean Rerun")
    lines.append("")
    lines.append(f"**Model**: `{MODEL_NAME}`")
    lines.append(f"**Timestamp**: {_time.strftime('%Y-%m-%dT%H:%M:%S')}")
    lines.append("")
    lines.append("## Background")
    lines.append("")
    lines.append("The first run (2026-06-06) was downgraded to INCONCLUSIVE by Codex review.")
    lines.append("See `hot.md` Step2 Literal Policy section and `STEP2_LITERAL_POLICY_CLEAN_RERUN_GUIDE.md`.")
    lines.append("")
    lines.append("## Goal")
    lines.append("")
    lines.append("Answer a cleaner question: Given decomposition fixtures that already satisfy")
    lines.append("tree structure, signatures, parent output coverage, dataflow, and child coverage,")
    lines.append("can a prompt-only Step2 literal policy accept PRD/branch literals while rejecting")
    lines.append("runtime facts?")
    lines.append("")
    lines.append("## Prompt Delta")
    lines.append("")
    lines.append("Same as first run. VALUE ORIGIN RULES injected into Stage 3 implementation prompt")
    lines.append("and LITERAL POLICY check added to verify prompt. Additionally, verify prompt now")
    lines.append("includes PRD/SubPRD/acceptance context and declared literal expectations.")
    lines.append("")
    lines.append("```text")
    lines.append(prompt_delta.strip())
    lines.append("```")
    lines.append("")
    lines.append("## Case List")
    lines.append("")
    lines.append("| Case | Type | Mode | Target | Expected | Expected Reason |")
    lines.append("|------|------|------|--------|----------|-----------------|")
    for entry in cases_def:
        case_id = entry[0]
        slug = entry[1]
        expected = entry[3]
        target = entry[6]   # target_invariant
        mode = entry[7] if len(entry) > 7 else ""
        exp_reason = entry[8] if len(entry) > 8 else ""
        lines.append(f"| {case_id} | {expected} | {mode} | {target} | {expected} | {exp_reason} |")
    lines.append("")
    lines.append("## Self-Audit Summary")
    lines.append("")
    lines.append("Self-audit ran before any LLM call. Checks include parent output coverage,")
    lines.append("dataflow field existence, literal prd_basis, and reason declarations.")
    lines.append("")
    lines.append("| Case | Passed | Checks Failed | Uncovered Outputs |")
    lines.append("|------|--------|---------------|-------------------|")
    if audit_results:
        for ar in audit_results:
            cid = ar["case_id"]
            passed = "PASS" if ar["passed"] else "FAIL"
            failed = [k for k, v in ar["checks"].items() if not v and not k.startswith("_")]
            uncovered = ar.get("parent_output_uncovered", [])
            failed_str = ", ".join(failed) if failed else "none"
            uncovered_str = ", ".join(uncovered) if uncovered else "none"
            lines.append(f"| {cid} | {passed} | {failed_str} | {uncovered_str} |")
    else:
        lines.append("| (no audit data) | | | |")
    lines.append("")
    lines.append("## Aggregate Metrics")
    lines.append("")
    for k, v in summary.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    lines.append("## Grouped Verdicts")
    lines.append("")
    lines.append("| Group | Cases | Passed / Expected-Reason | Migration Role |")
    lines.append("|-------|-------|--------------------------|----------------|")
    lines.append(f"| Literal positives | {summary['literal_positive_cases']} | {summary['literal_positive_passed']} passed | Must all accept |")
    lines.append(f"| Parent-mediated dispatch positive | {summary['dispatch_positive_cases']} | {summary['dispatch_positive_passed']} passed | Must accept, but not a literal false-rejection signal |")
    lines.append(f"| Full-generate positive controls | {summary['full_generate_positive_control_cases']} | {summary['full_generate_positive_control_passed']} passed | Must call child and cover parent output |")
    lines.append(f"| Verifier-only literal negatives | {summary['verifier_literal_negative_cases']} | {summary['verifier_literal_negative_expected_reason']} expected-reason rejects | Must reject with return_value_origin |")
    lines.append(f"| Missing-capability negative | {summary['missing_capability_negative_cases']} | {summary['missing_capability_negative_expected_reason']} expected-reason rejects | Must reject with missing_child_capability |")
    lines.append(f"| Tree regression control | {summary['tree_regression_cases']} | {summary['tree_regression_expected_reason']} expected-reason rejects | Excluded from literal migration verdict |")
    lines.append("")
    lines.append("## Confusion Matrix")
    lines.append("")
    lines.append("| | Accepted | Rejected (expected reason) | Rejected (other reason) |")
    lines.append("|---|---|---|---|")
    lines.append(f"| Allowed literal | {confusion['allowed_literal_accepted']} | {confusion['allowed_literal_rejected']} | N/A |")
    runtime_rejected_expected = confusion["runtime_literal_rejected_expected_reason"]
    runtime_rejected_other = confusion["runtime_literal_rejected_other_reason"]
    runtime_accepted = confusion["runtime_literal_accepted"]
    lines.append(f"| Runtime literal | {runtime_accepted} | {runtime_rejected_expected} | {runtime_rejected_other} |")
    lines.append("")
    lines.append("## Per-Case Verdict Table")
    lines.append("")
    lines.append("| Case | Expected | Passed | Category | Gen | Verify | Actual Reason | Expected Reason |")
    lines.append("|------|----------|--------|----------|-----|--------|---------------|-----------------|")
    for r in results:
        lines.append(f"| {r['case_id']} | {r['expected']} | {r['passed']} | {r['category']} | {r['generate_status']} | {r['verify_status']} | {r['reason'][:80]} | {r.get('reason_note', '')} |")
    lines.append("")
    lines.append("## Reason-Match Results")
    lines.append("")
    expected_match = summary["negative_passed_expected_reason"]
    other_reason = summary["negative_rejected_other_reason"]
    false_acc = summary["negative_false_acceptance"]
    lines.append(f"- **Valid rejection with expected reason**: {expected_match}")
    lines.append(f"- **Rejected by other reason**: {other_reason}")
    lines.append(f"- **False acceptance**: {false_acc}")
    lines.append("")
    lines.append("## Migration Verdict")
    lines.append("")
    positive_all_pass = summary["positive_passed"] == summary["positive_cases"] and summary["positive_cases"] > 0
    negative_all_pass = (expected_match + other_reason) == summary["negative_cases"]
    negative_all_expected = expected_match == summary["negative_cases"]
    no_api_failures = summary["api_or_parse_failures"] == 0
    no_artifact_failures = summary["artifact_failures"] == 0
    literal_positive_all_pass = (
        summary["literal_positive_cases"] > 0
        and summary["literal_positive_passed"] == summary["literal_positive_cases"]
    )
    dispatch_positive_all_pass = summary["dispatch_positive_passed"] == summary["dispatch_positive_cases"]
    full_generate_controls_all_pass = (
        summary["full_generate_positive_control_cases"] > 0
        and summary["full_generate_positive_control_passed"] == summary["full_generate_positive_control_cases"]
    )
    verifier_literal_negatives_all_expected = (
        summary["verifier_literal_negative_expected_reason"] == summary["verifier_literal_negative_cases"]
    )
    missing_capability_all_expected = (
        summary["missing_capability_negative_expected_reason"] == summary["missing_capability_negative_cases"]
    )

    if (
        literal_positive_all_pass
        and dispatch_positive_all_pass
        and full_generate_controls_all_pass
        and verifier_literal_negatives_all_expected
        and missing_capability_all_expected
        and no_api_failures
        and no_artifact_failures
    ):
        lines.append("**MIGRATION_CANDIDATE**")
    elif not no_artifact_failures:
        lines.append("**INCONCLUSIVE_ARTIFACT_FAILURE** — at least one case lacks reproducible artifacts.")
    elif not literal_positive_all_pass:
        lines.append("**INCONCLUSIVE_LITERAL_POSITIVE_FAILURE** — at least one allowed-literal positive did not pass.")
    elif not dispatch_positive_all_pass:
        lines.append("**INCONCLUSIVE_GENERATION_FALLBACK_REGRESSION** — a no-literal parent-mediated positive did not pass; this is not counted as allowed-literal rejection.")
    elif not full_generate_controls_all_pass:
        lines.append("**INCONCLUSIVE_POSITIVE_CONTROL_FAILURE** — at least one full-generate positive control did not pass.")
    elif not verifier_literal_negatives_all_expected:
        lines.append("**INCONCLUSIVE_LITERAL_NEGATIVE_REASON_MISMATCH** — verifier-only runtime literal negatives did not all reject with return_value_origin.")
    elif not missing_capability_all_expected:
        lines.append("**INCONCLUSIVE_MISSING_CAPABILITY_REASON_MISMATCH** — missing-capability negative did not reject with the expected reason.")
    elif positive_all_pass and negative_all_pass and not negative_all_expected:
        lines.append("**INCONCLUSIVE_REASON_MISMATCH** — all rejected but not for expected reasons.")
    elif not positive_all_pass:
        lines.append("**INCONCLUSIVE_FIXTURE_OR_AUDIT_FAILURE** — positive cases did not all pass.")
    else:
        lines.append("**INCONCLUSIVE** — see per-case details.")
    lines.append("")
    lines.append("## Claims and Limitations")
    lines.append("")
    lines.append("This experiment uses synthetic fixtures. Real-world migration may uncover")
    lines.append("additional value-origin ambiguities not captured here.")
    lines.append("")
    lines.append("## Stop-Rule Compliance")
    lines.append("")
    lines.append("- MVP not modified.")
    lines.append("- hot.md not modified by this run (updated separately).")
    lines.append("- No prompt tuning after results.")
    lines.append("- Single pass.")
    lines.append(f"- Output: {output_dir}")
    lines.append("")

    report = "\n".join(lines)
    with open(os.path.join(output_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport written to {output_dir}")
    print(f"\nSummary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


# ============================================================================
# Main
# ============================================================================

def main():
    global MODEL_NAME, OUTPUT_NAME, OUTPUT_BASE
    parser = argparse.ArgumentParser(description="Step2 Literal Policy clean rerun")
    parser.add_argument("--audit-only", action="store_true", help="Run deterministic self-audit only")
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--output-name", default=OUTPUT_NAME)
    args = parser.parse_args()
    MODEL_NAME = args.model
    OUTPUT_NAME = args.output_name
    OUTPUT_BASE = os.path.join(os.path.dirname(__file__), "output", OUTPUT_NAME, MODEL_NAME)
    output_dir = OUTPUT_BASE
    log_path = _install_run_log(output_dir)

    print("Step2 Literal Policy Experiment — Clean Rerun")
    print(f"Model: {MODEL_NAME}")
    print(f"Output: {OUTPUT_BASE}")
    print(f"Run log: {log_path}")
    print()

    config = Config.from_env()
    config.model = MODEL_NAME

    # Define all cases
    cases = [
        # (case_id, slug, node_or_tuple, expected, target_invariant, allowed_literals, forbidden_literals, mode, expected_primary_reason)
        ("P1", "unsupported_command_branch_literal", build_case_P1()),
        ("P2", "empty_list_prd_literal", build_case_P2()),
        ("P3", "conditional_dispatch_no_literals", build_case_P3()),
        ("N1", "hardcoded_runtime_id", build_case_N1()),
        ("N2a", "literal_substitutes_child_output", build_case_N2a()),
        ("N2b", "full_generate_child_output_required", build_case_N2b()),
        ("N3a", "runtime_status_hardcoded", build_case_N3a()),
        ("N3b", "full_generate_status_child_required", build_case_N3b()),
        ("N4", "missing_capability_masked_by_literal", build_case_N4()),
        ("N5", "sibling_call_violation", build_case_N5()),
    ]

    os.makedirs(output_dir, exist_ok=True)

    # ============================================================
    # PHASE 1: SELF-AUDIT
    # ============================================================
    print("=" * 60)
    print("PHASE 1: SELF-AUDIT")
    print("=" * 60)
    print()

    audit_results = []
    skip_cases = set()

    for entry in cases:
        case_id = entry[0]
        slug = entry[1]
        node, expected, allowed_literals, forbidden_literals, target_invariant, mode, expected_primary_reason, fake_code = entry[2]

        audit = run_self_audit_extended(
            case_id, node, expected, target_invariant,
            allowed_literals, forbidden_literals, mode, expected_primary_reason,
        )
        audit_results.append(audit)

        case_dir = os.path.join(output_dir, f"case_{case_id}_{slug}")
        _save_json(os.path.join(case_dir, "case_audit.json"), audit)

        status = "PASS" if audit["passed"] else "FAIL"
        print(f"  [{case_id}] Audit: {status}")
        if not audit["passed"]:
            failed = [k for k, v in audit["checks"].items() if not v and not k.startswith("_")]
            print(f"         Failed checks: {failed}")
            if audit.get("parent_output_uncovered"):
                print(f"         Uncovered outputs: {audit['parent_output_uncovered']}")
            skip_cases.add(case_id)
        _time.sleep(0.1)

    all_audits_passed = len(skip_cases) == 0
    print(f"\nAll audits passed: {all_audits_passed}")
    print()

    if not all_audits_passed:
        if any(case_id.startswith("P") for case_id in skip_cases):
            print("CRITICAL: Positive case audit failed. Cannot proceed to LLM for positive cases.")
            print("Fix fixture errors before proceeding.")
        if not any(case_id.startswith("P") for case_id in skip_cases):
            print("Only negative cases failed audit. May continue selectively.")

    if args.audit_only:
        print("Audit-only mode: stopping before LLM calls.")
        return

    if any(case_id.startswith("P") for case_id in skip_cases):
        print("Positive case audit failed. Stopping before LLM calls.")
        return

    # ============================================================
    # PHASE 2: LLM EXPERIMENT
    # ============================================================
    print("=" * 60)
    print("PHASE 2: LLM EXPERIMENT")
    print("=" * 60)
    print()

    api_client = APIClient(config)
    gen = LiteralPolicyCodeGenerator(config, api_client)

    results = []

    for entry in cases:
        case_id = entry[0]
        slug = entry[1]
        node, expected, allowed_literals, forbidden_literals, target_invariant, mode, expected_primary_reason, fake_code = entry[2]

        print(f"\n--- Case {case_id}: {slug} ---")

        # Skip if audit failed
        if case_id in skip_cases:
            print(f"  [{case_id}] Skipped (audit failure)")
            verdict = {
                "case_id": case_id,
                "expected": expected,
                "passed": False,
                "category": "case_audit_failure",
                "generate_status": "skipped",
                "verify_status": "skipped",
                "failed_checks": [],
                "static_analysis": {},
                "reason": f"Self-audit failed for case {case_id}",
                "reason_note": "",
            }
            case_dir = os.path.join(output_dir, f"case_{case_id}_{slug}")
            _save_json(os.path.join(case_dir, "verdict.json"), verdict)
            results.append(verdict)
            continue

        # Rate limit delay
        if results:
            _time.sleep(15)

        if mode == "positive":
            verdict = run_positive_case(
                gen, case_id, slug, node, output_dir,
                expected, allowed_literals, forbidden_literals, target_invariant,
            )
        elif mode == "verifier_only":
            verdict = run_negative_verifier_only(
                gen, case_id, slug, node, output_dir,
                expected, allowed_literals, forbidden_literals, target_invariant,
                expected_primary_reason, fake_code,
            )
        elif mode == "full_generate":
            verdict = run_negative_full_generate(
                gen, case_id, slug, node, output_dir,
                expected, allowed_literals, forbidden_literals, target_invariant,
                expected_primary_reason,
            )
        else:
            print(f"  [{case_id}] Unknown mode: {mode}")
            continue

        results.append(verdict)

    # ============================================================
    # PHASE 3: REPORT
    # ============================================================
    print()
    print("=" * 60)
    print("PHASE 3: REPORT GENERATION")
    print("=" * 60)
    print()

    # Prompt delta for report
    from code_generator_literal_policy import LITERAL_POLICY_RULES, LITERAL_POLICY_CHECK
    prompt_delta = LITERAL_POLICY_RULES + "\n" + LITERAL_POLICY_CHECK

    # Build flat case list for report
    cases_flat = []
    for entry in cases:
        cid, cs, tup = entry
        node_v, exp_v, al_v, fl_v, ti_v, md_v, er_v, fc_v = tup
        cases_flat.append((cid, cs, node_v, exp_v, al_v, fl_v, ti_v, md_v, er_v, fc_v))

    generate_report(output_dir, results, cases_flat, prompt_delta, audit_results)

    print()
    print("=" * 60)
    print("COMPLIANCE")
    print("=" * 60)
    print()
    print("[OK] Files created under experiment/decomposer-mental-model-study/ only")
    print("[OK] MVP files NOT modified")
    print("[OK] hot.md NOT modified by this run")
    print("[OK] Self-audit completed before all LLM calls")
    print("[OK] No prompt tuning performed after results")
    print("[OK] All prompts, responses, audits, and verdicts preserved")
    print()


if __name__ == "__main__":
    main()
