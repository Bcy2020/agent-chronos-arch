"""
Dataflow-aware CodeGenerator — experiment-only prototype.

Subclasses the MVP CodeGenerator and overrides parent prompt builders to:
1. Include structured DECLARED DATAFLOW EDGES as authoritative composition contract
2. Weaken DECOMPOSITION RATIONALE to non-authoritative supplementary context
3. Include child I/O source/consumer metadata
4. Add explicit parent-mediated composition rules
5. Include DATAFLOW CONFORMANCE check in verify prompt

Do NOT use this in production. This is an experiment-only file.
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from config import Config
from api_client import APIClient
from models import Node, DataflowEdge

# Import the MVP CodeGenerator
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "mvp", "mvp-0.4.4"))
from code_generator import CodeGenerator as MVPCodeGenerator


class DataflowAwareCodeGenerator(MVPCodeGenerator):
    """
    Experiment-only CodeGenerator that explicitly passes structured dataflow_edges
    to both the parent codegen prompt and the parent verify prompt.
    """

    def _build_dataflow_edges_table(self, edges: List[DataflowEdge]) -> str:
        """Render dataflow_edges as a structured table."""
        if not edges:
            return ""

        lines = [
            "",
            "=" * 60,
            "DECLARED DATAFLOW EDGES - AUTHORITATIVE COMPOSITION CONTRACT",
            "=" * 60,
            "",
            "Each row is a data transfer that the parent implementation must realize.",
            "Sibling-to-sibling rows describe data dependency only; they must be implemented by the parent:",
            "the parent calls the source child, stores its output, then passes the value to the target child.",
            "Children must never call siblings.",
            "",
            "| from_node | from_output | to_node | to_input | note |",
            "|-----------|-------------|---------|----------|------|",
        ]

        for e in edges:
            lines.append(
                f"| {e.from_node} | {e.from_output} | {e.to_node} | {e.to_input} | {e.note} |"
            )

        lines.append("")
        return "\n".join(lines)

    def _build_child_io_metadata(self, node: Node) -> str:
        """Build child I/O metadata section with source/consumer info."""
        lines = [
            "",
            "=" * 60,
            "CHILD I/O METADATA (source and consumer are authoritative)",
            "=" * 60,
        ]

        for child in (node.children or []):
            contract = node.children_contracts.get(child.name)
            if not contract:
                continue

            lines.append(f"")
            lines.append(f"  [{child.name}]")

            # Inputs with source metadata
            if contract.inputs:
                lines.append(f"    Inputs:")
                for inp in contract.inputs:
                    source = inp.source if inp.source else "unspecified"
                    lines.append(f"      - {inp.name}: {inp.type} (source: {source}) - {inp.description}")

            # Outputs with consumer metadata
            if contract.outputs:
                lines.append(f"    Outputs:")
                for out in contract.outputs:
                    consumer = out.consumer if out.consumer else "unspecified"
                    lines.append(f"      - {out.name}: {out.type} (consumer: {consumer}) - {out.description}")

        return "\n".join(lines)

    def _build_system_prompt_for_parent(self) -> str:
        """Override: add dataflow-aware rules to system prompt."""
        return """You are a decomposition verifier. Your role is to verify that a parent function CAN be correctly implemented by composing its child functions — and if so, to generate the implementation code. Code generation IS the verification method: if composition succeeds, the decomposition is valid; if it fails, the decomposition must be rejected.

WORKFLOW — THREE STAGES:

STAGE 1 — TREE STRUCTURE REVIEW (before writing any code):

First, verify the decomposition satisfies tree structure constraints. These are non-negotiable structural rules:

TREE STRUCTURE RULES:
1. **Child independence**: Each child node is an independent function. A child must NOT call, reference, or depend on any sibling node.
2. **Sibling invisibility**: Children operate at the same level and have no knowledge of each other. The decomposition tree ensures that sibling nodes are isolated — they cannot invoke each other's functions.
3. **Parent as sole orchestrator**: The parent node is the ONLY node that directly calls its children. The parent coordinates the workflow by invoking children in sequence or conditionally.
4. **Data flow goes through parent**: Data flow edges represent LOGICAL dependencies — the parent takes one child's output and passes it as input to another child. This is the normal pattern of parent orchestration and is NOT a violation. What IS forbidden is a child directly calling or invoking a sibling function.

TRUST THE STRUCTURE, NOT THE DESCRIPTION:
The tree structure is the authoritative representation of relationships. Base your verification on structural facts, not on how nodes describe themselves.
- Tree visualization is ground truth: All nodes at the same depth under the same parent ARE siblings. This is a structural fact that overrides any ambiguous wording in behavior descriptions.
- Behavior text naming siblings explicitly IS a violation: If a node's behavior says "calls CreateOrder" and CreateOrder is a sibling, that is a clear violation.
- Behavior text with ambiguous wording that implies sibling calling IS also a violation: If a node's behavior says "calls the handler child" but the tree shows all handlers as siblings at the same depth, the structure proves these handlers are NOT its children — the description is misleading, and what it describes IS sibling calling.
- Input source / output consumer fields are NOT evidence of direct calls: These show logical data flow that the parent resolves by passing data between children. Do not flag them.
- Generic processing terms are not violations: Words like "parse", "validate", "process", "calculate", "return result" without referencing specific sibling functions are normal single-node behavior.

DO NOT TRUST THE DECOMPOSER'S DESCRIPTION:
If a node's behavior describes calling or invoking other sibling nodes, that IS a violation regardless of how the decomposer frames it. The decomposer's narrative does not override structural reality.

If any tree structure check fails, the decomposition is invalid — return cannot_compose with reason "tree_structure_violation".

STAGE 2 — INTERFACE REVIEW (only if STAGE 1 passes):
Check whether the children's interfaces collectively satisfy ALL of the parent's requirements:
- Does every child input parameter have a clear source? (parent input, prior child output, or leaf capability)
- Can every parent output field be produced by combining child outputs?
- Is every needed data access covered by at least one child?
- Do the child signatures fit together without type mismatches?
If any check fails, the decomposition is invalid — return cannot_compose.

STAGE 2.5 — DATAFLOW EDGE CONFORMANCE (authoritative):
Check that the declared dataflow edges can be realized with the given child signatures:
- For each edge where from_node is a child and to_node is "parent": the child must have a matching output.
- For each edge where from_node is "parent" and to_node is a child: the child must have a matching input.
- For each child-to-child data dependency (from_node=ChildA, to_node=ChildB): the parent must mediate — the parent calls ChildA, stores its output, then passes it to ChildB. If the child signatures make this impossible, return cannot_compose.
Do NOT infer hidden routing from child names such as Route*, Dispatch*, Handler*, or Validate*; use the structured dataflow edges.

STAGE 3 — IMPLEMENT (only if STAGE 1, STAGE 2, and STAGE 2.5 pass):
Write the parent function by composing child calls. Rules:
1. You MUST implement the parent function by calling the child functions
2. Child functions are NOT implemented yet - you only have their interfaces
3. Use the child function signatures exactly as provided
4. The parent function's inputs/outputs must match the specification
5. You may use: conditionals, loops, local variables, helper logic
6. DO NOT directly read or write global state - delegate ALL data operations to child functions
7. Parent function should only orchestrate child calls, not perform data operations
8. CRITICAL — Every value in the parent's return statement MUST originate from a child output or a parent input.
   If a child is missing that should produce this data, the composition has failed.
9. CRITICAL — For each declared dataflow edge, the parent must realize the transfer:
   - If edge says ChildA.output -> parent.var, assign ChildA's output to parent.var
   - If edge says parent.var -> ChildB.input, pass parent.var to ChildB's input
   - If edge says ChildA.output -> ChildB.input, pass ChildA's output through parent to ChildB

SIGNATURE ENFORCEMENT - YOUR FUNCTION SIGNATURE IS LOCKED:
- Your function's parameter names, types, and return type are specified and non-negotiable
- The signature shown in the user prompt is the EXACT contract the caller expects
- Do NOT add, remove, or rename parameters
- Do NOT change parameter types or return type
- The verifier strictly checks signature compliance

DATA SOURCE OPERATIONS:
- Each child has declared data_operations that specify which data source it operates on
- The parent must NOT directly access any data source - only children can do that
- If you need to read/write data, ensure a child is responsible for it

The code you generate will be validated:
- It must be syntactically correct Python
- It must use the child function interfaces correctly
- It must NOT directly read/write any data source (only through child calls)
- It must preserve the parent's input/output contract
- It must realize every declared dataflow edge

Return ONLY valid JSON with this structure:
{
  "code": "def parent_function(...):\\n    ...",
  "status": "ok | cannot_compose",
  "imports": ["import os", "from typing import ..."],
  "child_calls": ["child1", "child2"],
  "implementation_notes": "Brief explanation of the logic",
  "decomposition_feedback": {
    "reason": "tree_structure_violation | missing_child_input_source | missing_child_capability | invalid_child_boundary | wrong_child_signature | cannot_satisfy_parent_output | dataflow_conformance_failure | other",
    "offending_child": "ChildName or empty",
    "violations": [
      {
        "from_node": "name of node that violates",
        "to_node": "name of node being called/referenced",
        "rule": "which rule is violated",
        "details": "why this is a violation"
      }
    ],
    "missing_inputs": [
      {
        "child": "ChildName",
        "param": "param_name",
        "why_needed": "why this input is needed",
        "expected_source": "parent input / previous child output / new child output"
      }
    ],
    "direct_resource_accesses": [
      {
        "resource": "resource_name",
        "operation": "read",
        "why_needed": "why this resource access is needed"
      }
    ],
    "suggested_fix": "Concrete suggestion for re-decomposition",
    "requires_redecomposition": true
  }
}"""

    def _build_system_prompt_for_parent_verify(self) -> str:
        """Override: add dataflow conformance check to verify prompt."""
        return """You are a senior code reviewer examining a code submission. The code below was written by another developer. Your job is to review whether the submitted parent function correctly uses the declared child functions — and based on that, judge whether the decomposition (the set of children) is valid.

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

If ANY check fails, return status="cannot_compose" with detailed feedback and list which checks failed in failed_checks.
If ALL checks pass, return status="ok" with empty checks marked passed.

Return ONLY valid JSON with this structure:
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
    "reason": "missing_child_input_source | missing_child_capability | invalid_child_boundary | wrong_child_signature | cannot_satisfy_parent_output | dataflow_conformance_failure | other",
    "offending_child": "ChildName or empty",
    "failed_checks": ["return_value_origin", "child_coverage"],
    "missing_inputs": [
      {
        "child": "ChildName",
        "param": "param_name",
        "why_needed": "why this input is needed",
        "expected_source": "parent input / previous child output / new child output"
      }
    ],
    "direct_resource_accesses": [
      {
        "resource": "resource_name",
        "operation": "read",
        "why_needed": "why this resource access is needed"
      }
    ],
    "suggested_fix": "Concrete suggestion for re-decomposition",
    "requires_redecomposition": true
  }
}"""

    def _build_user_prompt_for_parent(
        self,
        node: Node,
        previous_errors: List[str] = None,
        previous_code: str = None
    ) -> str:
        """Override: add structured dataflow edges and weaken rationale."""
        lines = [
            f"Implement the parent function by composing its child functions.",
            f"You MUST implement this as a single function, NOT a class.",
            f"",
            f"=" * 60,
            f"PARENT FUNCTION",
            f"=" * 60,
            f"Name: {node.name}",
            f"Purpose: {node.purpose}",
        ]

        # Add parent SubPRD information if available
        if node.subprd:
            if node.subprd.description:
                lines.append(f"")
                lines.append(f"Parent Task Description:")
                for line in node.subprd.description.split("\n"):
                    lines.append(f"  {line}")
            if node.subprd.constraints:
                lines.append(f"")
                lines.append(f"Parent Constraints:")
                for c in node.subprd.constraints:
                    lines.append(f"  - {c}")
            if node.subprd.global_state_operations:
                lines.append(f"")
                lines.append(f"Parent Global State Operations:")
                for op in node.subprd.global_state_operations:
                    lines.append(f"  - {op.op_type} on {op.source_id}: {op.op_id}")
                    if op.target:
                        lines.append(f"    Target: {op.target}")
            if node.subprd.traceability.parent_requirement_ids:
                lines.append(f"")
                lines.append(f"Parent Traces to: {', '.join(node.subprd.traceability.parent_requirement_ids)}")

        lines.append(f"")
        lines.append(f"Parent Inputs:")

        for inp in node.inputs:
            lines.append(f"  - {inp.name}: {inp.type} - {inp.description}")

        lines.append(f"Parent Outputs:")
        for out in node.outputs:
            lines.append(f"  - {out.name}: {out.type} - {out.description}")

        if node.data_sources:
            lines.append(f"")
            lines.append(f"Data Sources (Available Data Stores):")
            for ds in node.data_sources:
                lines.append(f"  - {ds.name} ({ds.category}, {ds.access})")
                lines.append(f"    Type: {ds.data_type}")
                lines.append(f"    Description: {ds.description}")

        if node.global_vars:
            lines.append(f"")
            lines.append(f"Global Variables:")
            for gv in node.global_vars:
                lines.append(f"  - {gv.op} on {gv.variable}: {gv.description}")

        lines.append(f"")
        lines.append(f"=" * 60)
        lines.append(f"CHILDREN - INTERFACES AND DATA OPERATIONS")
        lines.append(f"=" * 60)

        # Weaken decomposition rationale — make it non-authoritative
        if node.decomposition_rationale:
            lines.append(f"")
            lines.append(f"SUPPLEMENTARY RATIONALE (non-authoritative)")
            lines.append(f"Use this only as explanatory context. If it conflicts with DECLARED DATAFLOW EDGES, follow the structured dataflow edges.")
            lines.append(f"{node.decomposition_rationale}")

        lines.append(f"")
        lines.append(f"Child Functions (interfaces only, not implemented):")

        # Use node.children to access child Node objects for SubPRD info
        for child in (node.children or []):
            contract = node.children_contracts.get(child.name)
            if contract:
                lines.append(f"")
                lines.append(f"  [{child.name}]")
                lines.append(f"    Purpose: {contract.purpose}")
                lines.append(f"    Behavior: {contract.behavior}")

                if contract.signature:
                    lines.append(f"    Signature: {contract.signature}")
                else:
                    inputs_str = ", ".join([f"{i.name}: {i.type}" for i in contract.inputs])
                    outputs_str = ", ".join([o.type for o in contract.outputs]) if contract.outputs else "None"
                    lines.append(f"    Signature: def {child.name}({inputs_str}) -> {outputs_str}")

                # Include I/O source/consumer metadata
                if contract.inputs:
                    lines.append(f"    Inputs:")
                    for inp in contract.inputs:
                        source = inp.source if inp.source else "unspecified"
                        lines.append(f"      - {inp.name}: {inp.type} (source: {source}) - {inp.description}")

                if contract.outputs:
                    lines.append(f"    Outputs:")
                    for out in contract.outputs:
                        consumer = out.consumer if out.consumer else "unspecified"
                        lines.append(f"      - {out.name}: {out.type} (consumer: {consumer}) - {out.description}")

                if contract.data_operations:
                    lines.append(f"    Data Operations:")
                    for op in contract.data_operations:
                        lines.append(f"      - {op.source_name}: {op.operation_type} ({op.description})")

                if contract.preconditions:
                    lines.append(f"    Preconditions: {contract.preconditions}")
                if contract.postconditions:
                    lines.append(f"    Postconditions: {contract.postconditions}")

            # Add child SubPRD information
            if child.subprd:
                if child.subprd.global_state_operations:
                    for op in child.subprd.global_state_operations:
                        lines.append(f"    State Op: {op.op_type} on {op.source_id}")
                if child.subprd.acceptance_criteria:
                    for ac in child.subprd.acceptance_criteria:
                        lines.append(f"    Acceptance: {ac.description}")
                if child.subprd.traceability and child.subprd.traceability.parent_requirement_ids:
                    lines.append(f"    Traces: {', '.join(child.subprd.traceability.parent_requirement_ids)}")

        # Add structured dataflow edges — AUTHORITATIVE
        dataflow_section = self._build_dataflow_edges_table(node.dataflow_edges)
        if dataflow_section:
            lines.append(dataflow_section)

        if node.global_vars:
            lines.append(f"")
            lines.append(f"Global Variables:")
            for gv in node.global_vars:
                lines.append(f"  - {gv.op} on {gv.variable}: {gv.description}")

        if previous_errors:
            lines.append(f"")
            lines.append(f"=" * 60)
            lines.append(f"PREVIOUS CODE GENERATION FAILED WITH THESE ERRORS:")
            lines.append(f"=" * 60)
            for err in previous_errors:
                lines.append(f"  - {err}")
            if previous_code:
                lines.append(f"")
                lines.append(f"PREVIOUS CODE (please fix):")
                lines.append(f"```python")
                for line in previous_code.strip().split("\n"):
                    lines.append(f"  {line}")
                lines.append(f"```")
            lines.append(f"Please fix these issues in your new code.")

        schema_ref = self._build_schema_reference()
        if schema_ref:
            lines.append(schema_ref)

        lines.append(f"")
        lines.append(f"=" * 60)
        lines.append(f"PARENT-MEDIATED COMPOSITION RULES")
        lines.append(f"=" * 60)
        lines.append(f"- The parent is the only composition coordinator.")
        lines.append(f"- If a dataflow edge says ChildA -> ChildB, implement it as parent-mediated transfer:")
        lines.append(f"  a_out = ChildA(...); b_out = ChildB(a_out, ...)")
        lines.append(f"- A child must not call a sibling.")
        lines.append(f"- If the declared dataflow cannot be implemented with the declared child signatures, return cannot_compose.")
        lines.append(f"- Do not infer hidden routing from child names such as Route*, Dispatch*, Handler*, or Validate*;")
        lines.append(f"  use the structured dataflow edges.")

        lines.append(f"")
        lines.append(f"=" * 60)
        lines.append(f"INTERFACE ENFORCEMENT - LOCKED SIGNATURE")
        lines.append(f"=" * 60)
        lines.append(f"Your exact function signature is LOCKED and MUST be:")
        lines.append(f"  {node.get_interface_signature()}")
        lines.append(f"Do NOT change parameter names, types, or return type.")
        lines.append(f"Adding, removing, or renaming parameters will cause verification failure.")
        lines.append(f"")
        lines.append(f"=" * 60)
        lines.append(f"IMPLEMENTATION REQUIREMENTS")
        lines.append(f"=" * 60)
        lines.append(f"1. Generate ONLY a function definition, no classes")
        lines.append(f"2. Call the child functions with correct arguments")
        lines.append(f"3. Handle the return values from child functions")
        lines.append(f"4. Return a result that matches the parent outputs")
        lines.append(f"5. Realize every declared dataflow edge through parent-mediated transfer")
        lines.append(f"")

        return "\n".join(lines)

    def _build_user_prompt_for_parent_verify(
        self,
        node: Node,
        code: str
    ) -> str:
        """Override: add structured dataflow edges and conformance check."""
        lines = [
            f"Review the submitted code below. This code was written by another developer.",
            f"",
            f"=" * 60,
            f"SUBMITTED PARENT FUNCTION",
            f"=" * 60,
            f"Name: {node.name}",
            f"Purpose: {node.purpose}",
            f"",
            f"Parent Inputs:",
        ]
        for inp in node.inputs:
            lines.append(f"  - {inp.name}: {inp.type} - {inp.description}")
        lines.append(f"Parent Outputs:")
        for out in node.outputs:
            lines.append(f"  - {out.name}: {out.type} - {out.description}")

        if node.data_sources:
            lines.append(f"")
            lines.append(f"Data Sources:")
            for ds in node.data_sources:
                lines.append(f"  - {ds.name} ({ds.category}, {ds.access})")

        if node.global_vars:
            lines.append(f"")
            lines.append(f"Global Variables:")
            for gv in node.global_vars:
                lines.append(f"  - {gv.op} on {gv.variable}: {gv.description}")

        lines.append(f"")
        lines.append(f"=" * 60)
        lines.append(f"CHILDREN - INTERFACES")
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
                # Include I/O source/consumer
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

        # Add structured dataflow edges — AUTHORITATIVE
        dataflow_section = self._build_dataflow_edges_table(node.dataflow_edges)
        if dataflow_section:
            lines.append(dataflow_section)

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
