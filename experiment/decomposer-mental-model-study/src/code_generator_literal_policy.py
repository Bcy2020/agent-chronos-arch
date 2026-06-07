"""
Literal-policy-aware CodeGenerator — experiment-only prototype.

Subclasses DataflowAwareCodeGenerator and overrides parent prompt builders to:
1. Add VALUE ORIGIN RULES for hardcoded literals in Stage 3 implementation prompt
2. Add LITERAL POLICY CHECK in verify prompt

This tests whether a prompt-only patch can accept legitimate PRD/branch-conditioned
literals while still rejecting hardcoded runtime facts.

Do NOT use in production. This is an experiment-only file.
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from config import Config
from api_client import APIClient
from models import Node, DataflowEdge, CompositionFeedback
from code_generator_dataflow import DataflowAwareCodeGenerator


# The literal policy rules to inject into Stage 3 of the implementation prompt
LITERAL_POLICY_RULES = """
VALUE ORIGIN RULES FOR HARDCODED LITERALS:

You may use hardcoded literals only when the value is a PRD-defined constant,
an output-schema label, or a branch-conditioned fallback value directly entailed
by the current control-flow branch.

Allowed literals:
- fixed output keys such as "success", "message", "data"
- PRD-defined status strings, error messages, enum labels, or error codes
- branch-conditioned constants such as success=False for invalid input or
  "Unsupported command" for an unsupported-command branch
- empty containers only when the PRD or branch semantics permit an empty result

Forbidden literals:
- runtime facts such as ids, timestamps, counts, prices, inventory, payment
  results, order status, user records, messages, appointments, build logs, or
  any data that depends on parent input, child output, global state, or external
  systems
- any literal that substitutes for a child output
- any literal that hides a missing child capability or failed child call

Before returning a literal, classify it:
- PRD_LITERAL: fixed by PRD or output schema
- BRANCH_LITERAL: fixed by the current branch condition
- DYNAMIC_VALUE: must come from parent input, child output, computation, or data
  access

DYNAMIC_VALUE must never be hardcoded.
"""

# The literal policy check to inject into the verify prompt
LITERAL_POLICY_CHECK = """
5. LITERAL POLICY — Trace every literal value in every return statement and classify it:
   - PRD_LITERAL: The value is explicitly fixed by the PRD, SubPRD, or output schema
     (e.g., fixed output keys like "success", "message"; PRD-defined status strings,
     error codes, enum labels).
   - BRANCH_LITERAL: The value is a fallback constant directly entailed by the current
     control-flow branch condition (e.g., success=False when the input is invalid,
     "Unsupported command" when the command is not in the supported set, empty list when
     the PRD says "return empty if no records found" AND the code already called the
     relevant child to determine emptiness).
   - DYNAMIC_VALUE: The value depends on runtime data — parent input, child output,
     computation, global state, or external system. DYNAMIC_VALUE literals are FORBIDDEN.

   A literal is FORBIDDEN if:
   - It represents a runtime fact (id, timestamp, count, price, inventory, payment
     result, order status, user record, message, appointment, build log, etc.)
   - It substitutes for a child function's output (e.g., returning total=0.0 when
     CalculateTotal child exists and should be called)
   - It hides a missing child capability (e.g., returning an error message for a
     payment path when no payment child exists)
   - It is a DYNAMIC_VALUE masquerading as a branch literal (e.g., returning
     status="delivered" under an order-status branch when the status must come from
     a child call)

   If ANY forbidden literal is found, return status="cannot_compose" with reason
   "return_value_origin" and list the forbidden literals.
"""


class LiteralPolicyCodeGenerator(DataflowAwareCodeGenerator):
    """
    Experiment-only CodeGenerator that patches both the implementation prompt and
    the verify prompt with VALUE ORIGIN RULES for hardcoded literals.

    Inherits dataflow-aware behavior from DataflowAwareCodeGenerator.
    """

    def generate_for_parent(
        self,
        node: Node,
        previous_errors: List[str] = None,
        previous_code: str = None
    ) -> Tuple[str, List[str]]:
        """Override only to persist prompts/raw responses for experiment artifacts."""
        self.last_gen_prompt = ""
        self.last_gen_response = ""
        self.last_gen_parsed = None
        self.last_verify_prompt = ""
        self.last_verify_response = ""
        self.last_verify_parsed = None
        self.last_composition_feedback = None

        if not node.children:
            return "", ["Cannot generate parent code: no children defined"]

        messages = [
            {"role": "system", "content": self._build_system_prompt_for_parent()},
            {"role": "user", "content": self._build_user_prompt_for_parent(node, previous_errors, previous_code)}
        ]
        self.last_gen_prompt = messages[0]["content"] + "\n\n---\n\n" + messages[1]["content"]

        try:
            response = self.api_client.chat(messages, max_tokens=2048)
        except Exception as e:
            return "", [f"API call failed: {e}"]
        self.last_gen_response = response

        parsed = self._parse_response(response)
        self.last_gen_parsed = parsed
        status = parsed.get("status", "ok")
        if status == "cannot_compose":
            feedback_data = parsed.get("decomposition_feedback", {})
            feedback_data["status"] = "cannot_compose"
            feedback_data["checks"] = parsed.get("checks", {})
            self.last_composition_feedback = CompositionFeedback.from_dict(feedback_data)
            return "", [f"CANNOT_COMPOSE: {self.last_composition_feedback.reason}"]

        if "error" in parsed or not parsed.get("code"):
            return "", [f"Failed to parse code: {parsed.get('error', 'No code generated')}"]

        code = parsed.get("code", "")
        verify_messages = [
            {"role": "system", "content": self._build_system_prompt_for_parent_verify()},
            {"role": "user", "content": self._build_user_prompt_for_parent_verify(node, code)}
        ]
        self.last_verify_prompt = verify_messages[0]["content"] + "\n\n---\n\n" + verify_messages[1]["content"]

        try:
            verify_response = self.api_client.chat(verify_messages, max_tokens=1024)
        except Exception as e:
            print(f"Verification step failed, accepting step 1 code: {e}")
            return code, []
        self.last_verify_response = verify_response

        verify_parsed = self._parse_response(verify_response)
        self.last_verify_parsed = verify_parsed
        verify_status = verify_parsed.get("status", "ok")
        verify_checks = verify_parsed.get("checks", {})
        if verify_status == "cannot_compose":
            feedback_data = verify_parsed.get("decomposition_feedback", {})
            feedback_data["status"] = "cannot_compose"
            feedback_data["checks"] = verify_checks
            self.last_composition_feedback = CompositionFeedback.from_dict(feedback_data)
            return "", [f"CANNOT_COMPOSE: {feedback_data.get('reason', 'Verification rejected code')}"]

        return code, []

    def _build_system_prompt_for_parent(self) -> str:
        """Override: inject literal policy rules into Stage 3."""
        base = super()._build_system_prompt_for_parent()

        # Inject literal policy rules after the existing Stage 3 rule 9
        insertion_marker = (
            "9. CRITICAL — For each declared dataflow edge, the parent must realize the transfer:\n"
            "   - If edge says ChildA.output -> parent.var, assign ChildA's output to parent.var\n"
            "   - If edge says parent.var -> ChildB.input, pass parent.var to ChildB's input\n"
            "   - If edge says ChildA.output -> ChildB.input, pass ChildA's output through parent to ChildB"
        )

        if insertion_marker in base:
            base = base.replace(
                insertion_marker,
                insertion_marker + "\n10." + LITERAL_POLICY_RULES
            )
        else:
            base = base + "\n" + LITERAL_POLICY_RULES

        return base

    def _build_system_prompt_for_parent_verify(self) -> str:
        """Override: add literal policy check to verify checklist."""
        base = super()._build_system_prompt_for_parent_verify()

        marker = "If ANY check fails, return status=\"cannot_compose\""
        if marker in base:
            base = base.replace(
                marker,
                LITERAL_POLICY_CHECK + "\n" + marker
            )
        else:
            base = base + "\n" + LITERAL_POLICY_CHECK

        return base

    def _build_user_prompt_for_parent_verify(
        self,
        node: Node,
        code: str
    ) -> str:
        """Override: add PRD/SubPRD/acceptance context so verifier can judge literals."""
        lines = [
            f"Review the submitted code below. This code was written by another developer.",
            f"",
            f"=" * 60,
            f"SUBMITTED PARENT FUNCTION",
            f"=" * 60,
            f"Name: {node.name}",
            f"Purpose: {node.purpose}",
            f"",
        ]

        # SubPRD context — required for verifier to know what literals are authorized
        if node.subprd:
            lines.append(f"=" * 60)
            lines.append(f"PARENT SUBPRD — TASK DEFINITION")
            lines.append(f"=" * 60)
            if node.subprd.purpose:
                lines.append(f"Purpose: {node.subprd.purpose}")
            if node.subprd.description:
                lines.append(f"Description: {node.subprd.description}")
            if node.subprd.constraints:
                lines.append(f"Constraints:")
                for c in node.subprd.constraints:
                    for k, v in c.items() if isinstance(c, dict) else [("", c)]:
                        lines.append(f"  - {k}: {v}" if k else f"  - {v}")
            if node.subprd.acceptance_criteria:
                lines.append(f"Acceptance Criteria:")
                for ac in node.subprd.acceptance_criteria:
                    lines.append(f"  - [{ac.ac_id}] {ac.description}")
            lines.append(f"")

        # Declared literal expectations — tell the verifier explicitly what is allowed
        # These are injected dynamically by the experiment harness; stored as a checkpoint attr
        lit_exp = getattr(node, "_literal_expectations", None)
        if lit_exp:
            lines.append(f"=" * 60)
            lines.append(f"DECLARED LITERAL EXPECTATIONS FOR THIS CASE")
            lines.append(f"=" * 60)
            allowed_list = lit_exp.get("allowed", [])
            if allowed_list:
                lines.append(f"Allowed literals (authorized by PRD/SubPRD):")
                for al in allowed_list:
                    val = al.get("value", "")
                    kind = al.get("kind", "")
                    cond = al.get("condition", "")
                    prd = al.get("prd_basis", "")
                    lines.append(f"  - value={val!r}, kind={kind}")
                    lines.append(f"    condition: {cond}")
                    lines.append(f"    prd_basis: {prd}")
            forbidden_list = lit_exp.get("forbidden", [])
            if forbidden_list:
                lines.append(f"Forbidden literals (must be rejected):")
                for fl in forbidden_list:
                    val = fl.get("value", "")
                    kind = fl.get("kind", "")
                    reason = fl.get("reason", "")
                    lines.append(f"  - value={val!r}, kind={kind}")
                    lines.append(f"    reason: {reason}")
            lines.append(f"")

        # Parent I/O
        lines.append(f"Parent Inputs:")
        for inp in node.inputs:
            lines.append(f"  - {inp.name}: {inp.type} - {inp.description}")
        lines.append(f"Parent Outputs:")
        for out in node.outputs:
            lines.append(f"  - {out.name}: {out.type} - {out.description}")

        if node.data_sources:
            lines.append(f"Data Sources:")
            for ds in node.data_sources:
                lines.append(f"  - {ds.name} ({ds.category}, {ds.access})")

        # Children with full contract info
        lines.append(f"")
        lines.append(f"=" * 60)
        lines.append(f"CHILDREN — INTERFACES AND DATA OPERATIONS")
        lines.append(f"=" * 60)
        for child in (node.children or []):
            contract = node.children_contracts.get(child.name)
            if contract:
                lines.append(f"")
                lines.append(f"  [{child.name}]")
                lines.append(f"    Purpose: {contract.purpose}")
                lines.append(f"    Behavior: {contract.behavior}")
                if contract.signature:
                    lines.append(f"    Signature: {contract.signature}")
                if contract.inputs:
                    lines.append(f"    Inputs:")
                    for inp in contract.inputs:
                        source = inp.source if inp.source else "unspecified"
                        lines.append(f"      - {inp.name}: {inp.type} (source: {source})")
                if contract.outputs:
                    lines.append(f"    Outputs:")
                    for out in contract.outputs:
                        consumer = out.consumer if out.consumer else "unspecified"
                        lines.append(f"      - {out.name}: {out.type} (consumer: {consumer})")
                if contract.data_operations:
                    lines.append(f"    Data Operations:")
                    for op in contract.data_operations:
                        lines.append(f"      - {op.source_name}: {op.operation_type} ({op.description})")

        # Dataflow edges
        dataflow_section = self._build_dataflow_edges_table(node.dataflow_edges)
        if dataflow_section:
            lines.append(dataflow_section)

        # Generated code
        lines.append(f"")
        lines.append(f"=" * 60)
        lines.append(f"GENERATED CODE TO VERIFY")
        lines.append(f"=" * 60)
        lines.append(f"```python")
        lines.append(code.strip())
        lines.append(f"```")
        lines.append(f"")
        lines.append(f"Apply the verification checklist. Return your verdict as valid JSON.")
        return "\n".join(lines)
