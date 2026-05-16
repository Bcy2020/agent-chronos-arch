"""
CodeGenerator LLM: Generates Python code for a node.
- For parent nodes: composes child node interfaces
- For leaf nodes: generates complete implementation
- For leaf nodes with granted capabilities: uses interface-based prompt
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from config import Config
from api_client import APIClient
from models import Node, ChildContract, SubPRD, CapabilityGrant, InterfacePlan, InterfaceSpec, CompositionFeedback


class CodeGenerator:
    def __init__(self, config: Config, api_client: APIClient):
        self.config = config
        self.api_client = api_client
        self._interface_map: Dict[str, InterfaceSpec] = {}
        self._resource_schemas: Dict[str, Dict[str, Any]] = {}
    
    def _build_system_prompt_for_parent(self) -> str:
        return """You are a decomposition verifier. Your role is to verify that a parent function CAN be correctly implemented by composing its child functions — and if so, to generate the implementation code. Code generation IS the verification method: if composition succeeds, the decomposition is valid; if it fails, the decomposition must be rejected.

WORKFLOW — THREE STAGES:

STAGE 1 — REVIEW (before writing any code):
Intuitively check whether the children's interfaces collectively satisfy ALL of the parent's requirements:
- Does every child input parameter have a clear source? (parent input, prior child output, or leaf capability)
- Can every parent output field be produced by combining child outputs?
- Is every needed data access covered by at least one child?
- Do the child signatures fit together without type mismatches?
If any check fails, the decomposition is invalid — return cannot_compose.

STAGE 2 — IMPLEMENT (only if STAGE 1 passes):
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

Return ONLY valid JSON with this structure:
{
  "code": "def parent_function(...):\\n    ...",
  "status": "ok | cannot_compose",
  "imports": ["import os", "from typing import ..."],
  "child_calls": ["child1", "child2"],
  "implementation_notes": "Brief explanation of the logic",
  "decomposition_feedback": {
    "reason": "missing_child_input_source | missing_child_capability | invalid_child_boundary | wrong_child_signature | cannot_satisfy_parent_output | other",
    "offending_child": "ChildName or empty",
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
        return """You are a decomposition verifier. Verify the generated parent code against ALL rules below. Include a verdict for EVERY check in the JSON output.

RULES:
1. CHILD COVERAGE — Every child function must appear as a DIRECT CALL in the code (look for "ChildName("). A child called indirectly through another child is a VIOLATION.
2. RETURN VALUE ORIGIN — Every value in every return statement must trace to a child output or a parent input. Bare literals (None, True, "", 0, [], {}) that should come from a child are VIOLATIONS.
3. DIRECT ACCESS — The code must NOT directly read or write any global variable or data source. All data operations must go through child calls.

After evaluating ALL three rules, return:
- status="cannot_compose" if ANY rule found a violation
- status="ok" if ALL rules passed

Return ONLY valid JSON:
{
  "status": "ok | cannot_compose",
  "checks": {
    "child_coverage": {"passed": false, "details": "List each child: PASS/VIOLATION"},
    "return_value_origin": {"passed": true, "details": "Trace each return value"},
    "direct_access": {"passed": true, "details": "Check each global var / data source"}
  },
  "decomposition_feedback": {
    "reason": "missing_child_input_source | missing_child_capability | invalid_child_boundary | wrong_child_signature | cannot_satisfy_parent_output | other",
    "offending_child": "ChildName or empty",
    "missing_inputs": [{"child": "ChildName", "param": "param_name", "why_needed": "", "expected_source": ""}],
    "direct_resource_accesses": [{"resource": "", "operation": "", "why_needed": ""}],
    "suggested_fix": "Fix covering ALL violations found",
    "requires_redecomposition": true
  }
}"""

    def _build_system_prompt_for_leaf(self) -> str:
        return """You are a Python code generator. Your task is to implement a complete function.

CRITICAL RULES:
1. Generate a complete, working implementation
2. Use standard Python libraries (os, json, datetime, typing, etc.)
3. Handle edge cases and errors appropriately
4. Follow the function's purpose and behavior specification
5. If this node has data_operations, you are responsible for performing them on the specified data source
6. Use the declared data source operations EXACTLY as specified - do not invent new operations

SIGNATURE ENFORCEMENT - YOUR FUNCTION SIGNATURE IS LOCKED:
- Your function's parameter names, types, and return type are specified and non-negotiable
- The signature shown in the user prompt is the EXACT contract the parent expects
- Do NOT add, remove, or rename parameters
- Do NOT change parameter types or return type
- The verifier strictly checks signature compliance

DATA SOURCE OPERATIONS:
- If data_operations are declared, you MUST perform them on the specified data source
- Only use the allowed operations (read, write, read_write) for each data source
- Access the global variable using its declared name
- The data type tells you how to structure the data (dict, list, object, etc.)

The code you generate will be validated:
- It must be syntactically correct Python
- It must match the specified inputs/outputs
- It must perform only the declared data operations
- It should handle the described behavior

Return ONLY valid JSON with this structure:
{
  "code": "def function_name(...):\\n    ...",
  "imports": ["import os", "from typing import ..."],
  "dependencies": ["os", "json"],
  "implementation_notes": "Brief explanation"
}"""
    
    def _build_user_prompt_for_parent(
        self,
        node: Node,
        previous_errors: List[str] = None,
        previous_code: str = None
    ) -> str:
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

        if node.decomposition_rationale:
            lines.append(f"")
            lines.append(f"DECOMPOSITION RATIONALE (how children collaborate):")
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
        lines.append(f"")

        return "\n".join(lines)

    def _build_user_prompt_for_parent_verify(
        self,
        node: Node,
        code: str
    ) -> str:
        lines = [
            f"Verify the generated parent function code below.",
            f"",
            f"=" * 60,
            f"PARENT FUNCTION",
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
                if contract.data_operations:
                    lines.append(f"    Data Operations:")
                    for op in contract.data_operations:
                        lines.append(f"      - {op.source_name}: {op.operation_type} ({op.description})")

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

    def _build_user_prompt_for_leaf(
        self, 
        node: Node, 
        previous_errors: List[str] = None,
        previous_code: str = None
    ) -> str:
        lines = [
            f"Implement this function:",
            f"",
            f"Function: {node.name}",
            f"Purpose: {node.purpose}",
            f"",
        ]

        if node.subprd:
            if node.subprd.description:
                lines.append(f"Task Description:")
                for line in node.subprd.description.split("\n"):
                    lines.append(f"  {line}")
            if node.subprd.constraints:
                lines.append(f"Constraints:")
                for c in node.subprd.constraints:
                    lines.append(f"  - {c}")
            if node.subprd.global_state_operations:
                lines.append(f"Global State Operations:")
                for op in node.subprd.global_state_operations:
                    lines.append(f"  - {op.op_type} on {op.source_id}: {op.op_id}")
                    if op.target:
                        lines.append(f"    Target: {op.target}")
            if node.subprd.acceptance_criteria:
                lines.append(f"Acceptance Criteria:")
                for ac in node.subprd.acceptance_criteria:
                    lines.append(f"  - {ac.ac_id}: {ac.description}")
            if node.subprd.traceability.parent_requirement_ids:
                lines.append(f"Traces to: {', '.join(node.subprd.traceability.parent_requirement_ids)}")
            lines.append(f"")

        lines.append(f"Inputs:")
        
        for inp in node.inputs:
            lines.append(f"  {inp.name}: {inp.type} - {inp.description}")
        
        lines.append(f"Outputs:")
        for out in node.outputs:
            lines.append(f"  {out.name}: {out.type} - {out.description}")
        
        if node.boundary.in_scope:
            lines.append(f"In Scope: {node.boundary.in_scope}")
        if node.boundary.out_of_scope:
            lines.append(f"Out of Scope: {node.boundary.out_of_scope}")
        
        if node.preconditions:
            lines.append(f"Preconditions: {node.preconditions}")
        if node.postconditions:
            lines.append(f"Postconditions: {node.postconditions}")

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

        if previous_errors:
            lines.append(f"")
            lines.append(f"PREVIOUS CODE GENERATION FAILED WITH THESE ERRORS:")
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
        lines.append(f"IMPLEMENTATION")
        lines.append(f"=" * 60)
        lines.append(f"Generate a complete implementation.")
        
        return "\n".join(lines)

    def _build_system_prompt_for_leaf_with_interfaces(self) -> str:
        return """You are a Python code generator. Your task is to implement a function using only granted data interfaces.

WORKFLOW — TWO STAGES:

STAGE 1 — CAPABILITY COVERAGE REVIEW (before writing any code):
Carefully examine the function's purpose, inputs, outputs, and data requirements against
the granted interfaces below. Ask yourself:
- Can every data access, read, write, or query this function needs be satisfied by
  at least one of the granted interfaces?
- Is there any data operation the function's contract requires that no granted
  interface provides?
- Can the function's outputs be produced using ONLY the granted interfaces?

If the answer to ALL questions is YES, proceed to STAGE 2.
If the answer to ANY question is NO, the capabilities are INSUFFICIENT.
Do NOT attempt to generate code. Do NOT invent interfaces or use ungranted ones.
Return status="insufficient_capabilities" with detailed capability_gap_feedback
describing which interfaces are missing and why.

STAGE 2 — IMPLEMENT (only if STAGE 1 passes):
Generate code following these rules:
1. You have been granted specific data access interfaces — use ONLY those.
2. Do NOT declare or access global variables directly (no 'global' keyword).
3. Do NOT use operation IDs (op_root_*) or source IDs.
4. Do NOT invent new resource access functions — only use the granted ones.
5. You can use standard Python libraries (os, json, datetime, typing, etc.).
6. Call the granted interface functions as normal function calls (they are imported externally).
7. Handle edge cases and errors appropriately.
8. Dict key names MUST match the Data Schema Reference exactly (e.g., use order['total_price'], not order['total']).

SIGNATURE ENFORCEMENT - YOUR FUNCTION SIGNATURE IS LOCKED:
- Your function's parameter names, types, and return type are specified and non-negotiable.
- The signature shown in the user prompt is the EXACT contract the parent expects.
- Do NOT add, remove, or rename parameters.
- Do NOT change parameter types or return type.
- The verifier strictly checks signature compliance.

The code you generate will be validated:
- It must be syntactically correct Python.
- It must match the specified inputs/outputs.
- It must use only the granted interfaces for data access.
- It must NOT use the 'global' keyword.
- It must NOT reference op_root_* or source_id variables.

Return ONLY valid JSON with this structure:
{
  "status": "ok | insufficient_capabilities",
  "code": "def function_name(...):\\n    ...",
  "imports": ["import os", "from typing import ..."],
  "dependencies": ["os", "json"],
  "implementation_notes": "Brief explanation",
  "capability_gap_feedback": {
    "reason": "missing_read_interface | missing_write_interface | missing_query_capability | other",
    "missing_interfaces": [
      {
        "interface_id": "resource.operation",
        "why_needed": "why this interface is needed"
      }
    ],
    "suggested_fix": "Concrete suggestion for which interface to add to InterfacePlan or how to re-decompose.",
    "requires_redecomposition": true
  }
}

When status is "ok", omit capability_gap_feedback or set to null.
When status is "insufficient_capabilities", set code to "" and populate capability_gap_feedback.
When status is "insufficient_capabilities", do NOT attempt to generate any code."""

    def _build_user_prompt_for_leaf_with_interfaces(
        self,
        node: Node,
        previous_errors: List[str] = None,
        previous_code: str = None
    ) -> str:
        lines = [
            f"Implement this function using only the granted interfaces:",
            f"",
            f"Function: {node.name}",
            f"Purpose: {node.purpose}",
            f"",
        ]

        if node.subprd:
            if node.subprd.description:
                lines.append(f"Task Description:")
                for line in node.subprd.description.split("\n"):
                    lines.append(f"  {line}")
            if node.subprd.constraints:
                lines.append(f"Constraints:")
                for c in node.subprd.constraints:
                    lines.append(f"  - {c}")
            if node.subprd.acceptance_criteria:
                lines.append(f"Acceptance Criteria:")
                for ac in node.subprd.acceptance_criteria:
                    lines.append(f"  - {ac.ac_id}: {ac.description}")
            lines.append(f"")

        lines.append(f"Inputs:")
        for inp in node.inputs:
            lines.append(f"  {inp.name}: {inp.type} - {inp.description}")

        lines.append(f"Outputs:")
        for out in node.outputs:
            lines.append(f"  {out.name}: {out.type} - {out.description}")

        if node.boundary.in_scope:
            lines.append(f"In Scope: {node.boundary.in_scope}")
        if node.boundary.out_of_scope:
            lines.append(f"Out of Scope: {node.boundary.out_of_scope}")

        if node.preconditions:
            lines.append(f"Preconditions: {node.preconditions}")
        if node.postconditions:
            lines.append(f"Postconditions: {node.postconditions}")

        if node.granted_capabilities and node.granted_capabilities.granted_interfaces:
            lines.append(f"")
            lines.append(f"=" * 60)
            lines.append(f"GRANTED DATA INTERFACES (use ONLY these):")
            lines.append(f"=" * 60)
            for interface_id in node.granted_capabilities.granted_interfaces:
                iface = self._interface_map.get(interface_id)
                if iface:
                    lines.append(f"  - {iface.signature}")
                    lines.append(f"    Description: {iface.description}")
                    if iface.signature:
                        lines.append(f"    Signature: {iface.signature}")
                else:
                    lines.append(f"  - {interface_id}")
            lines.append(f"")
            lines.append(f" >>> Call these functions directly by name. They are available in scope. <<<")
            lines.append(f" >>> Do NOT declare 'global' variables. Do NOT use op_root_*. <<<")

        schema_ref = self._build_schema_reference()
        if schema_ref:
            lines.append(schema_ref)

        if previous_errors:
            lines.append(f"")
            lines.append(f"PREVIOUS CODE GENERATION FAILED WITH THESE ERRORS:")
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

        lines.append(f"")
        lines.append(f"=" * 60)
        lines.append(f"INTERFACE ENFORCEMENT - LOCKED SIGNATURE")
        lines.append(f"=" * 60)
        lines.append(f"Your exact function signature is LOCKED and MUST be:")
        lines.append(f"  {node.get_interface_signature()}")
        lines.append(f"Do NOT change parameter names, types, or return type.")
        lines.append(f"")
        lines.append(f"=" * 60)
        lines.append(f"IMPLEMENTATION")
        lines.append(f"=" * 60)
        lines.append(f"Generate a complete implementation using ONLY the granted interfaces above.")

        return "\n".join(lines)
    
    def _parse_response(self, content: str) -> Dict[str, Any]:
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```[a-zA-Z0-9]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            code_match = re.search(r'"code"\s*:\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
            if code_match:
                code = code_match.group(1)
                code = code.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')
                return {"code": code}
            
            if 'def ' in content:
                return {"code": content}
            
            return {"code": "", "error": str(e)}
    
    def generate_for_parent(
        self,
        node: Node,
        previous_errors: List[str] = None,
        previous_code: str = None
    ) -> Tuple[str, List[str]]:
        """
        Generate code for a parent node by composing child interfaces.
        Two-step process:
          Step 1: REVIEW + IMPLEMENT — generate code via child composition
          Step 2: VERIFY — send generated code for self-review, chance to reject
        Returns (code, errors).
        """
        if not node.children:
            return "", ["Cannot generate parent code: no children defined"]

        # Step 1: REVIEW + IMPLEMENT
        messages = [
            {"role": "system", "content": self._build_system_prompt_for_parent()},
            {"role": "user", "content": self._build_user_prompt_for_parent(node, previous_errors, previous_code)}
        ]

        try:
            response = self.api_client.chat(messages, max_tokens=2048)
        except Exception as e:
            return "", [f"API call failed: {e}"]

        parsed = self._parse_response(response)
        status = parsed.get("status", "ok")
        node.composition_feedback = None

        if status == "cannot_compose":
            feedback_data = parsed.get("decomposition_feedback", {})
            feedback_data["status"] = "cannot_compose"
            node.composition_feedback = CompositionFeedback.from_dict(feedback_data)
            return "", [f"CANNOT_COMPOSE: {node.composition_feedback.reason}"]

        if "error" in parsed or not parsed.get("code"):
            return "", [f"Failed to parse code: {parsed.get('error', 'No code generated')}"]

        code = parsed.get("code", "")

        # Step 2: VERIFY the generated code
        verify_messages = [
            {"role": "system", "content": self._build_system_prompt_for_parent_verify()},
            {"role": "user", "content": self._build_user_prompt_for_parent_verify(node, code)}
        ]

        try:
            verify_response = self.api_client.chat(verify_messages, max_tokens=1024)
        except Exception as e:
            print(f"Verification step failed, accepting step 1 code: {e}")
            return code, []

        verify_parsed = self._parse_response(verify_response)
        verify_status = verify_parsed.get("status", "ok")

        if verify_status == "cannot_compose":
            feedback_data = verify_parsed.get("decomposition_feedback", {})
            feedback_data["status"] = "cannot_compose"
            node.composition_feedback = CompositionFeedback.from_dict(feedback_data)
            return "", [f"CANNOT_COMPOSE: {feedback_data.get('reason', 'Verification rejected code')}"]

        return code, []
    
    def generate_for_leaf(
        self, 
        node: Node, 
        previous_errors: List[str] = None,
        previous_code: str = None
    ) -> Tuple[str, List[str]]:
        """
        Generate complete code for a leaf node.
        If node has granted_capabilities, uses interface-based prompt.
        Returns (code, errors).
        """
        if node.granted_capabilities and node.granted_capabilities.granted_interfaces:
            messages = [
                {"role": "system", "content": self._build_system_prompt_for_leaf_with_interfaces()},
                {"role": "user", "content": self._build_user_prompt_for_leaf_with_interfaces(node, previous_errors, previous_code)}
            ]
        else:
            messages = [
                {"role": "system", "content": self._build_system_prompt_for_leaf()},
                {"role": "user", "content": self._build_user_prompt_for_leaf(node, previous_errors, previous_code)}
            ]
        
        try:
            response = self.api_client.chat(messages, max_tokens=2048)
        except Exception as e:
            return "", [f"API call failed: {e}"]

        parsed = self._parse_response(response)
        status = parsed.get("status", "ok")
        node.composition_feedback = None

        if status == "insufficient_capabilities":
            feedback_data = parsed.get("capability_gap_feedback", {})
            feedback_data["status"] = "insufficient_capabilities"
            if "missing_interfaces" not in feedback_data:
                feedback_data["missing_interfaces"] = []
            node.composition_feedback = CompositionFeedback.from_dict(feedback_data)
            reason = feedback_data.get("reason", "No reason given")
            return "", [f"INSUFFICIENT_CAPABILITIES: {reason}"]

        if "error" in parsed or not parsed.get("code"):
            return "", [f"Failed to parse code: {parsed.get('error', 'No code generated')}"]

        return parsed.get("code", ""), []
    
    def set_interface_plan(self, plan: InterfacePlan) -> None:
        for iface in plan.interfaces:
            self._interface_map[iface.interface_id] = iface
        for resource in plan.resources:
            self._resource_schemas[resource.resource_id] = {
                "description": resource.description,
                "storage_model": resource.storage_model,
                "item_schema": resource.item_schema,
                "invariants": resource.invariants,
            }

    def _build_schema_reference(self) -> str:
        """Build a schema reference block for LLM prompts."""
        if not self._resource_schemas:
            return ""
        lines = [
            "",
            "=" * 60,
            "DATA SCHEMA REFERENCE (use these EXACT field names when accessing dict keys)",
            "=" * 60,
        ]
        for resource_id, schema_info in self._resource_schemas.items():
            lines.append(f"  {resource_id} dict fields:")
            for field, field_type in schema_info.get("item_schema", {}).items():
                lines.append(f"    - {field}: {field_type}")
            if schema_info.get("invariants"):
                for inv in schema_info["invariants"]:
                    lines.append(f"    (invariant) {inv}")
        lines.append("")
        lines.append(">>> When accessing a dict field, ALWAYS use the exact field name from the schema above. <<<")
        lines.append(">>> If a schema is listed under 'orders dict fields', then 'order' should use those fields. <<<")
        lines.append("")
        return "\n".join(lines)

    def generate(
        self,
        node: Node,
        previous_errors: List[str] = None,
        previous_code: str = None
    ) -> Tuple[str, List[str]]:
        """
        Generate code for any node.
        Returns (code, errors).
        """
        if node.stop_decompose or not node.children:
            return self.generate_for_leaf(node, previous_errors, previous_code)
        else:
            return self.generate_for_parent(node, previous_errors, previous_code)
    
    def generate_with_retry(
        self, 
        node: Node, 
        max_retries: int = None,
        previous_errors: List[str] = None,
        previous_code: str = None
    ) -> Tuple[str, List[str]]:
        """
        Generate code with retry on failure.
        When previous_errors/previous_code are provided (from validation feedback),
        they are injected into the first attempt's prompt.
        After each failed retry, accumulated errors are passed back.
        """
        retries = max_retries if max_retries is not None else self.config.max_decompose_retries
        all_errors = previous_errors or []
        all_previous_code = previous_code

        for attempt in range(retries):
            code, errors = self.generate(node, all_errors if (attempt > 0 or previous_errors) else None, all_previous_code)

            if errors and any(e.startswith("CANNOT_COMPOSE") for e in errors):
                return "", errors

            if errors and any(e.startswith("INSUFFICIENT_CAPABILITIES") for e in errors):
                return "", errors

            if not errors:
                return code, []

            all_errors = errors
            all_previous_code = code
            print(f"Code generation attempt {attempt + 1} failed: {errors}")

        return "", all_errors
