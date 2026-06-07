"""
Decomposer LLM: Decomposes a node into child nodes.
"""
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from config import Config
from api_client import APIClient
from models import Node, InputParam, OutputParam, Boundary, GlobalVar, ChildContract, DataSource, DataOperation, SubPRD, Traceability, AcceptanceCriterion, DataflowEdge


class Decomposer:
    def __init__(self, config: Config, api_client: APIClient):
        self.config = config
        self.api_client = api_client
        self.last_response: str = ""
    
    def _build_system_prompt(self) -> str:
        return """You are a software system decomposition agent. Your task is to decompose a function block into smaller child function blocks.

CRITICAL RULES - ENFORCED:
1. EVERY CHILD MUST BE A FUNCTION, NOT A CLASS. Never generate class definitions for child blocks.
2. Each child must have explicit: name, purpose, inputs, outputs, and boundary
3. Preserve the parent's external interface - children's composition must match parent's inputs/outputs
4. TREE STRUCTURE (not graph): The decomposition forms a tree, not a graph. Children MUST NOT call each other (no cross-calls between siblings). The parent MUST explicitly and directly invoke all its children. A coordinator child node is ALLOWED, as long as it only coordinates work within its own subtree and never calls sibling nodes.
5. Do NOT add extra external inputs or outputs beyond what the parent has
6. Children should be at the same abstraction level and minimally overlapping

SIGNATURE LOCKING - CHILD INTERFACES ARE BINDING CONTRACTS:
- Each child's declared inputs/outputs become a LOCKED signature that code generators MUST follow exactly
- Use precise Python types: str, int, float, bool, dict, list, Optional[dict], List[str], Dict[int, str], Tuple[str, int], Any, None
- Do NOT invent unnecessary parameters - a child should only receive what it needs to do its job
- Do NOT use generic "Any" when a specific type is known - precision enables signature validation
- Example CORRECT: inputs=[{"name": "task_id", "type": "int", "description": "ID of the task to validate"}]
- Example WRONG:   inputs=[{"name": "task_id", "type": "Any", "description": "the task id"}]
- The verifier will reject code that does not match the declared signature exactly

SEMANTIC STOP CONDITIONS - Use these instead of line-count estimation:
STOP DECOMPOSITION when the node is ONE of the following types:

1. PURE FUNCTION: The node performs only mathematical transformations with no:
   - Global/state variable dependencies (except parameters)
   - I/O operations (file, network, database)
   - Side effects or state modifications
   Example: calculate_totals(prices, tax_rate) -> total

2. ATOMIC OPERATION: The node performs exactly one operation on exactly one data source:
   - Read from a single data source (database, cache, file)
   - Write to a single data source
   - Read-modify-write on a single data source
   Example: reserve_inventory(product_id, quantity) -> bool

3. MAXIMUM DEPTH REACHED: Tree has reached the configured maximum depth

DO NOT STOP if the node:
- Contains business logic, branching, or loops
- Coordinates multiple child operations
- Transforms data between multiple sources
- Contains conditional validation logic

DATAFLOW CLOSURE RULES:
1. Every child input must have an explicit source.
2. A child input source must be one of:
   - a parent input,
   - an output of an earlier sibling child,
   - a local constant/config value explicitly described,
   - data obtained inside that same leaf through requested_capabilities.
3. If a child needs data that no previous child outputs and no parent input provides, add a child before it to produce that data, or move the data access inside that child as a leaf capability.
4. Do not create child signatures with dangling parameters such as products_data unless a previous child outputs products_data.
5. Parent must not directly access global state or data interfaces — all data operations must go through child function calls.

OUTPUT FORMAT - You MUST return valid JSON with this exact structure:
{
  "children": [
    {
      "name": "ChildName",
      "purpose": "Clear description of what this child function does",
      "inputs": [{"name": "param", "type": "str", "description": "desc", "source": "where data comes from"}],
      "outputs": [{"name": "result", "type": "int", "description": "desc", "consumer": "who uses this output"}],
      "boundary": {"in_scope": ["..."], "out_of_scope": ["..."]},
      "preconditions": ["..."],
      "postconditions": ["..."],
      "behavior": "Detailed description of expected behavior - how this function transforms inputs to outputs",
      "signature": "def ChildName(param1: type1, param2: type2) -> return_type",
      "stop_decompose": false,
      "stop_reason": "",
      "node_type": "pure_function|atomic_operation",
      "data_operations": [
        {"source_name": "data_source_name", "operation_type": "read|write|read_write", "description": "what operation is performed"}
      ],
      "constraints": [{"constraint_id": "C-001", "description": "constraint description"}],
      "acceptance_criteria": [{"ac_id": "AC-001", "description": "criterion description", "verification_method": "automated_test"}],
      "global_vars": [
        {"variable": "data_store_name", "op": "read|write|read_write", "description": "what operation is needed"}
      ],
      "traceability": {"parent_requirement_ids": ["FR-001"], "derived_from": "root"},
      "requested_capabilities": ["resource.operation", "resource.operation"]
    }
  ],
  "data_sources": [
    {"name": "source_name", "category": "database|file|cache|external|memory", "access": "read|write|read_write", "data_type": "dict|list|object", "description": "description"}
  ],
  "decomposition_rationale": "CRITICAL: Explain HOW these children work together to implement the parent. Describe the interaction flow, data transformation, and how they collectively cover ALL parent responsibilities. This is required for the code generator to understand how to compose these functions.",
  "interface_preservation": {
    "parent_inputs_covered_by": {"input_name": "child_name"},
    "parent_outputs_produced_by": {"output_name": "child_name"}
  },
  "dataflow_edges": [
    {
      "from_node": "parent | ChildName",
      "from_output": "parent_input_or_child_output_name",
      "to_node": "ChildName | parent",
      "to_input": "child_input_or_parent_output_name",
      "note": "why this dataflow exists"
    }
  ]
}

CRITICAL GLOBAL VARIABLES DISTRIBUTION RULE:
The parent's "global_vars" declares which data variables the subtree operates on and what operations are needed (read/write/read_write).
You MUST distribute these global_vars among children based on their responsibilities:
- A child that performs read/write on a variable declares the corresponding "global_vars"
- Each child's global_vars MUST be a subset of the parent's global_vars
- The union of all children's global_vars MUST cover all of the parent's declared operations on each variable"""
    
    # ========================================================================
    # Three-Stage Decomposition prompts
    # ========================================================================

    def _build_stage1_system_prompt(self) -> str:
        return """You are a software system decomposition agent. Your task is Stage 1: decompose a function block into child function blocks — STRUCTURE ONLY. Do NOT derive interfaces or resources.

CRITICAL RULES:
1. EVERY CHILD MUST BE A FUNCTION, NOT A CLASS.
2. TREE STRUCTURE (not graph): Children MUST NOT call each other. The parent MUST directly invoke all children.
3. Do NOT add extra external inputs or outputs beyond what the parent has.
4. Children should be at the same abstraction level and minimally overlapping.

DO NOT ASSUME TRADITIONAL DEVELOPMENT PATTERNS:
- DO NOT create "dispatcher", "router", "controller", "command_handler" nodes.
- DO NOT use Command Pattern, Strategy Pattern, or any pattern where one child calls other children.
- Each child MUST be a self-contained function that does actual work.
- The parent IS the router. If different inputs need different processing, the parent decides through conditional logic which child to call.
- The purpose of decomposition is to divide work, not to recreate enterprise architecture patterns.

SEMANTIC STOP CONDITIONS: STOP when pure function, atomic operation, or max depth reached.

OUTPUT FORMAT — Return valid JSON:
{
  "children": [
    {
      "name": "ChildName",
      "purpose": "semantic responsibility",
      "behavior": "internal transformation without sibling calls — describe WHAT this child does",
      "boundary": {"in_scope": ["..."], "out_of_scope": ["..."]},
      "semantic_inputs": [{"name": "...", "description": "...", "source": "parent input | previous child output | constant | internal leaf access"}],
      "semantic_outputs": [{"name": "...", "description": "...", "consumer": "parent | ChildName"}],
      "preconditions": ["..."],
      "postconditions": ["..."],
      "guarantees": ["..."],
      "composition_role": "transform | validate | decide | execute | aggregate | query | mutate",
      "stop_decompose": false,
      "stop_reason": ""
    }
  ],
  "decomposition_rationale": "how children jointly cover parent responsibility",
  "orchestration_model": "sequence | conditional | aggregate | pipeline | mixed",
  "dataflow_sketch": [{"from": "parent | ChildName", "to": "ChildName | parent", "data": "semantic data name", "note": "why"}]
}

CONSTRAINTS — FIELDS YOU MUST NOT EMIT:
- Do NOT emit "inputs", "outputs", "signature" — these belong to Stage 2.
- Do NOT emit "global_vars", "data_operations", "requested_capabilities", "constraints", "acceptance_criteria", "traceability" — these belong to Stage 3.
- Do NOT emit "dataflow_edges" — Stage 2 will derive dataflow from your dataflow_sketch.
- Do NOT emit "node_type" — Stage 3 will classify.
- Do NOT emit "interface_preservation" — Stage 2 will determine interface preservation.
- semantic_inputs/semantic_outputs are SEMANTIC descriptions only, NOT typed interfaces.
- composition_role=decide means "returns a decision to parent", not "calls another child"."""

    def _build_stage2_system_prompt(self) -> str:
        return """You are an interface derivation agent. Given a frozen Stage 1 decomposition, derive precise typed interfaces for each child.

RULES:
1. You MUST NOT add, delete, rename, or reorder children. The child list from Stage 1 is LOCKED.
2. You MUST NOT change any Stage 1 field: purpose, behavior, boundary, preconditions, postconditions, guarantees, composition_role.
3. Derive ONLY: inputs, outputs, signature, dataflow_edges, interface_preservation.
4. Separate parent-call parameters from internal leaf resource access.

REQUIRED INTERFACE CATEGORIES:
- inputs: Parameters the parent must pass when calling this child. Use precise Python types.
- outputs: Values returned by the child to the parent. Use precise Python types.
- signature: Python function signature built from inputs/outputs.
- dataflow_edges: Structured edges showing how data flows between parent and children.

INTERNAL LEAF ACCESS:
- If a semantic_input has source "internal leaf access", it describes data the child accesses inside its own implementation. DO NOT include it in inputs or signature — the child handles it internally.
- Only semantic inputs with source "parent input" or "previous child output" or "constant" become call inputs.

SIGNATURE LOCKING:
- Use precise Python types: str, int, float, bool, dict, list, Optional[dict], List[str], Dict[int, str], Tuple[str, int], Any, None.
- Do NOT use generic "Any" when a specific type is known.

DATAFLOW EDGES:
- from_node must be "parent" or exact child name (never a resource name like "orders", "messages").
- to_node must be "parent" or exact child name.
- Each edge describes a single data item that the parent must transfer.

OUTPUT FORMAT — Return valid JSON:
{
  "children": [
    {
      "name": "ChildName (UNCHANGED from Stage 1)",
      "purpose": "(UNCHANGED)",
      "behavior": "(UNCHANGED)",
      "boundary": {"in_scope": ["(UNCHANGED)"], "out_of_scope": ["(UNCHANGED)"]},
      "preconditions": ["(UNCHANGED)"],
      "postconditions": ["(UNCHANGED)"],
      "guarantees": ["(UNCHANGED)"],
      "composition_role": "(UNCHANGED)",
      "stop_decompose": false,
      "stop_reason": "",
      "inputs": [{"name": "param", "type": "str", "description": "desc", "source": "parent | parent input | previous child output | constant"}],
      "outputs": [{"name": "result", "type": "dict", "description": "desc", "consumer": "parent | ChildName"}],
      "signature": "def ChildName(param1: type1) -> return_type"
    }
  ],
  "interface_preservation": {"parent_inputs_covered_by": {}, "parent_outputs_produced_by": {}},
  "dataflow_edges": [{"from_node": "parent|ChildName", "from_output": "", "to_node": "ChildName|parent", "to_input": "", "note": ""}]
}"""

    def _build_stage3_system_prompt(self) -> str:
        return """You are a governance and resource derivation agent. Given frozen Stage 1 + Stage 2, derive resource allocation and governance fields for each child.

RULES:
1. You MUST NOT add, delete, rename, or reorder children. The child list from Stage 1/2 is LOCKED.
2. You MUST NOT change any Stage 1 field or Stage 2 interface (inputs, outputs, signature, dataflow_edges).
3. Derive ONLY: global_vars, data_operations, requested_capabilities, constraints, acceptance_criteria, traceability, node_type.

GLOBAL STATE CONSERVATION — HARD REQUIREMENT:
The parent's global_vars are an architectural contract. You MUST distribute them to children.
For every parent global var, the union of all child global_vars MUST cover the parent's required operation.
If parent requires read_write on X, children must collectively cover both read and write on X.
It is valid to assign read and write to different children, but neither side may disappear.
A child global_vars variable must come from parent global_vars — do not invent new variables.
data_operations should be consistent with global_vars.
requested_capabilities are RESOURCE OPERATION BUDGETS, not concrete InterfacePlan ids.
Use "resource.read", "resource.write", or "resource.read_write" to describe what
the child is allowed to access. Do NOT choose concrete interface ids here; leaf
implementation will select concrete interfaces later from the allowed budget.
Do not silently drop any parent operation.

SELF-CHECK before returning JSON:
- List every parent global var and its required op.
- For each, confirm which child (or children) covers it.
- If any parent op is unassigned, fix it before responding.

SYNCHRONIZATION RULE:
- If a child has data_operations on a resource, its global_vars must contain the same resource/op.
- If a child has global_vars on a resource, its data_operations must reflect the same access.

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
      "global_vars": [{"variable": "var_name", "op": "read|write|read_write", "description": "what operation is needed"}],
      "data_operations": [{"source_name": "source", "operation_type": "read|write|read_write", "description": "what operation is performed"}],
      "requested_capabilities": ["resource.operation"],
      "constraints": [{"constraint_id": "C-001", "description": "constraint description"}],
      "acceptance_criteria": [{"ac_id": "AC-001", "description": "criterion description", "verification_method": "automated_test"}],
      "traceability": {"parent_requirement_ids": ["FR-001"]},
      "node_type": "pure_function|atomic_operation",
      "stop_decompose": false,
      "stop_reason": ""
    }
  ],
  "governance_notes": "explain how conservation is satisfied"
}"""

    def _build_stage1_user_prompt(self, node: Node, previous_errors: Any = None, interface_plan_summary: str = "") -> str:
        """Stage 1 user prompt: structure-only decomposition context."""
        prompt_parts = [
            "Stage 1 — Decompose into child functions. Output STRUCTURE ONLY (no interfaces, no resources).",
            "",
            f"Node Name: {node.name}",
            f"Node Purpose: {node.purpose}",
            "",
        ]

        if node.subprd:
            if node.subprd.description:
                prompt_parts.append(f"Task Description:")
                for line in node.subprd.description.split("\n"):
                    prompt_parts.append(f"  {line}")
            if node.subprd.constraints:
                prompt_parts.append(f"Constraints:")
                for c in node.subprd.constraints:
                    cid = c.get('constraint_id', c.get('description', '')) if isinstance(c, dict) else str(c)
                    cdesc = c.get('description', c) if isinstance(c, dict) else str(c)
                    prompt_parts.append(f"  - {cid}: {cdesc}")
            prompt_parts.append("")

        prompt_parts.append(f"Inputs:")
        for inp in node.inputs:
            prompt_parts.append(f"  - {inp.name}: {inp.type} - {inp.description}")

        prompt_parts.append(f"Outputs:")
        for out in node.outputs:
            prompt_parts.append(f"  - {out.name}: {out.type} - {out.description}")

        prompt_parts.append(f"Boundary:")
        prompt_parts.append(f"  In Scope: {', '.join(node.boundary.in_scope)}")
        prompt_parts.append(f"  Out of Scope: {', '.join(node.boundary.out_of_scope)}")

        if node.data_sources:
            prompt_parts.append("")
            prompt_parts.append("Data Sources (AVAILABLE DATA STORES):")
            for ds in node.data_sources:
                prompt_parts.append(f"  - {ds.name} ({ds.category}, {ds.access}): {ds.description}")

        if node.global_vars:
            prompt_parts.append("")
            prompt_parts.append("Global Variables (for context — Stage 3 will distribute these):")
            for gv in node.global_vars:
                prompt_parts.append(f"  - {gv.op} on {gv.variable}: {gv.description}")

        if node.preconditions:
            prompt_parts.append(f"Preconditions: {node.preconditions}")
        if node.postconditions:
            prompt_parts.append(f"Postconditions: {node.postconditions}")

        if previous_errors:
            prompt_parts.append("")
            prompt_parts.append(self._format_previous_errors(previous_errors))

        prompt_parts.append("")
        prompt_parts.append(f"Maximum children allowed: {self.config.max_children}")
        prompt_parts.append(f"Maximum depth: {self.config.max_depth}")
        prompt_parts.append("Return ONLY the JSON response with structure fields (name, purpose, behavior, boundary, semantic_inputs, semantic_outputs, composition_role).")
        prompt_parts.append("Do NOT include inputs, outputs, signature, global_vars, data_operations, or dataflow_edges.")

        return "\n".join(prompt_parts)

    def _build_stage2_user_prompt(self, node: Node, stage1_data: Dict, previous_errors: Any = None) -> str:
        """Stage 2 user prompt: derive interfaces from Stage 1 structure."""
        children = stage1_data.get("children", [])
        lines = [
            "Stage 2 — Derive typed interfaces for each child.",
            "The child list from Stage 1 is FROZEN. Do NOT add, delete, rename, or reorder children.",
            "",
            f"Parent: {node.name}",
            f"Purpose: {node.purpose}",
            "",
            "Parent Inputs:",
        ]
        for inp in node.inputs:
            lines.append(f"  - {inp.name}: {inp.type} - {inp.description}")
        lines.append("Parent Outputs:")
        for out in node.outputs:
            lines.append(f"  - {out.name}: {out.type} - {out.description}")
        lines.append("")

        if node.data_sources:
            lines.append("Available Data Stores:")
            for ds in node.data_sources:
                lines.append(f"  - {ds.name} ({ds.category}, {ds.access})")
            lines.append("")

        lines.append("Children (frozen from Stage 1):")
        for c in children:
            lines.append(f"  {c.get('name', '')}: {c.get('purpose', '')}")
            lines.append(f"    behavior: {c.get('behavior', '')[:200]}")
            lines.append(f"    composition_role: {c.get('composition_role', '')}")
            if c.get('semantic_inputs'):
                lines.append(f"    semantic_inputs:")
                for si in c['semantic_inputs']:
                    lines.append(f"      - {si.get('name','')}: {si.get('description','')} (source: {si.get('source','')})")
            if c.get('semantic_outputs'):
                lines.append(f"    semantic_outputs:")
                for so in c['semantic_outputs']:
                    lines.append(f"      - {so.get('name','')}: {so.get('description','')} (consumer: {so.get('consumer','')})")
        lines.append("")

        # Include dataflow_sketch from Stage 1 for reference
        dataflow_sketch = stage1_data.get("dataflow_sketch", [])
        if dataflow_sketch:
            lines.append("Dataflow Sketch (from Stage 1 — use as guide for dataflow_edges):")
            for ds in dataflow_sketch:
                lines.append(f"  {ds.get('from','')}.{ds.get('data','')} -> {ds.get('to','')} ({ds.get('note','')})")
            lines.append("")
            lines.append("Convert this sketch into structured dataflow_edges with precise field names.")
            lines.append("from_node/to_node must be 'parent' or exact child name, NOT resource names.")
            lines.append("")

        if previous_errors:
            lines.append(self._format_previous_errors(previous_errors))

        lines.append("Return ONLY the JSON response.")
        return "\n".join(lines)

    def _build_stage3_user_prompt(self, node: Node, stage1_data: Dict, stage2_data: Dict, previous_errors: Any = None) -> str:
        """Stage 3 user prompt: derive resources and governance from Stage 1+2."""
        # Use Stage 2 children if available (they have the interfaces), else Stage 1
        stage2_children = stage2_data.get("children", stage1_data.get("children", []))
        lines = [
            "Stage 3 — Derive governance and resource fields for each child.",
            "The child list from Stage 1/2 is FROZEN. Do NOT add, delete, rename, or reorder children.",
            "",
            f"Parent: {node.name}",
            f"Purpose: {node.purpose}",
            "",
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
        for c in stage2_children:
            lines.append(f"  {c.get('name', '')}: {c.get('purpose', '')}")
            sig = c.get("signature", "")
            if sig:
                lines.append(f"    signature: {sig}")
            if c.get("inputs"):
                input_strs = []
                for inp in c['inputs']:
                    n = inp.get('name', '')
                    t = inp.get('type', '')
                    input_strs.append(f"{n}: {t}")
                lines.append(f"    inputs: {', '.join(input_strs)}")
            if c.get("dataflow_edges") or stage2_data.get("dataflow_edges"):
                pass  # dataflow edges are in stage2_data, shown below
        lines.append("")

        # Show dataflow edges from Stage 2
        edges = stage2_data.get("dataflow_edges", [])
        if edges:
            lines.append("Dataflow Edges (from Stage 2):")
            for e in edges:
                lines.append(f"  {e.get('from_node','')}.{e.get('from_output','')} -> {e.get('to_node','')}.{e.get('to_input','')}")
            lines.append("")

        if previous_errors:
            lines.append(self._format_previous_errors(previous_errors))

        lines.append("Return ONLY the JSON response.")
        return "\n".join(lines)

    def _format_previous_errors(self, previous_errors: Any) -> str:
        """Format previous errors for inclusion in any stage user prompt."""
        parts = []
        if isinstance(previous_errors, dict):
            parts.append("=== PREVIOUS ATTEMPT DIAGNOSTICS ===")
            if previous_errors.get("previous_children"):
                parts.append(f"  Previous children: {previous_errors['previous_children']}")
            if previous_errors.get("previous_rationale"):
                parts.append(f"  Previous rationale: {previous_errors['previous_rationale'][:300]}")
            if previous_errors.get("validator_report"):
                vr = previous_errors["validator_report"]
                if vr.get("unused_children"):
                    parts.append(f"  Children NOT called: {vr['unused_children']}")
                if vr.get("composition_feedback"):
                    parts.append(f"  Codegen rejected composition:")
                    parts.append(json.dumps(vr["composition_feedback"], ensure_ascii=False, indent=4))
                if vr.get("structured_errors"):
                    parts.append(f"  Structured errors:")
                    parts.append(json.dumps(vr["structured_errors"], ensure_ascii=False, indent=4))
            if previous_errors.get("previous_errors"):
                for err in previous_errors["previous_errors"]:
                    parts.append(f"  - {err}")
            parts.append("")
            parts.append("DIAGNOSIS: The previous decomposition did not compose cleanly.")
            parts.append("Repair the child boundaries and dataflow. Restart from Stage 1 structure.")
        else:
            parts.append("PREVIOUS DECOMPOSITION FAILED:")
            for err in (previous_errors if isinstance(previous_errors, list) else [str(previous_errors)]):
                parts.append(f"  - {err}")
            parts.append("Please fix these issues in your new decomposition.")
        return "\n".join(parts)

    def _build_user_prompt(self, node: Node, previous_errors: Any = None, interface_plan_summary: str = "") -> str:
        prompt_parts = [
            f"Decompose the following function block:",
            f"",
            f"Node Name: {node.name}",
            f"Node Purpose: {node.purpose}",
            f"",
        ]

        if node.subprd:
            prompt_parts.append(f"SubPRD Context:")
            if node.subprd.description:
                prompt_parts.append(f"  Task Description:")
                for line in node.subprd.description.split("\n"):
                    prompt_parts.append(f"    {line}")
            if node.subprd.constraints:
                prompt_parts.append(f"  Constraints:")
                for c in node.subprd.constraints:
                    prompt_parts.append(f"    - {c.get('constraint_id', c.get('description', ''))}: {c.get('description', '')}")
            if node.subprd.acceptance_criteria:
                prompt_parts.append(f"  Acceptance Criteria:")
                for ac in node.subprd.acceptance_criteria:
                    prompt_parts.append(f"    - {ac.ac_id}: {ac.description}")
            if node.subprd.traceability.parent_requirement_ids:
                prompt_parts.append(f"  Traces to: {', '.join(node.subprd.traceability.parent_requirement_ids)}")
            prompt_parts.append(f"")

        prompt_parts.append(f"Inputs:")

        for inp in node.inputs:
            prompt_parts.append(f"  - {inp.name}: {inp.type} - {inp.description}")

        prompt_parts.append(f"Outputs:")
        for out in node.outputs:
            prompt_parts.append(f"  - {out.name}: {out.type} - {out.description}")

        prompt_parts.append(f"Boundary:")
        prompt_parts.append(f"  In Scope: {', '.join(node.boundary.in_scope)}")
        prompt_parts.append(f"  Out of Scope: {', '.join(node.boundary.out_of_scope)}")

        if node.data_sources:
            prompt_parts.append(f"")
            prompt_parts.append(f"Data Sources (AVAILABLE DATA STORES):")
            for ds in node.data_sources:
                prompt_parts.append(f"  - {ds.name} ({ds.category}, {ds.access}): {ds.description}")
                if ds.data_type:
                    prompt_parts.append(f"    Data Type: {ds.data_type}")

        if node.global_vars:
            prompt_parts.append(f"")
            prompt_parts.append(f"Global Variables (MUST be DISTRIBUTED to children):")
            for gv in node.global_vars:
                prompt_parts.append(f"  - {gv.op} on {gv.variable}: {gv.description}")
            prompt_parts.append(f"")
            prompt_parts.append(f"  >>> Each child must declare a SUBSET of these global_vars in the 'global_vars' field. <<<")
            prompt_parts.append(f"  >>> Children perform actual data operations; parent orchestrates by calling children. <<<")

        if node.preconditions:
            prompt_parts.append(f"Preconditions: {node.preconditions}")
        if node.postconditions:
            prompt_parts.append(f"Postconditions: {node.postconditions}")

        if interface_plan_summary:
            prompt_parts.append(f"")
            prompt_parts.append(f"Available Data Interfaces (context only; do NOT copy interface ids into 'requested_capabilities'):")
            prompt_parts.append(interface_plan_summary)
            prompt_parts.append(f"")
            prompt_parts.append(f"  >>> Each child that needs data access MUST list resource operation budgets in 'requested_capabilities'. <<<")
            prompt_parts.append(f"  >>> Use resource.read, resource.write, or resource.read_write; leaf codegen will choose concrete interfaces later. <<<")
            prompt_parts.append(f"  >>> A leaf that uses 'requested_capabilities' will NOT declare global_vars. <<<")

        if previous_errors:
            prompt_parts.append(f"")
            if isinstance(previous_errors, dict):
                prompt_parts.append(f"=== PREVIOUS ATTEMPT DIAGNOSTICS ===")
                if previous_errors.get("previous_children"):
                    prompt_parts.append(f"  Previous children you produced: {previous_errors['previous_children']}")
                if previous_errors.get("previous_rationale"):
                    prompt_parts.append(f"  Your previous rationale: {previous_errors['previous_rationale'][:300]}")
                if previous_errors.get("previous_code"):
                    prompt_parts.append(f"  Generated parent code was:")
                    for line in previous_errors['previous_code'].split("\n")[:15]:
                        prompt_parts.append(f"    | {line}")
                if previous_errors.get("validator_report"):
                    vr = previous_errors["validator_report"]
                    prompt_parts.append(f"  Validator found:")
                    if vr.get("unused_children"):
                        prompt_parts.append(f"    - Children NOT called: {vr['unused_children']}")
                    if vr.get("actual_calls"):
                        prompt_parts.append(f"    - Children actually called: {vr['actual_calls']}")
                    if vr.get("error_type"):
                        prompt_parts.append(f"    - Error type: {vr['error_type']}")
                    if vr.get("fix_summary"):
                        prompt_parts.append(f"    Fix summary:")
                        prompt_parts.append(json.dumps(vr["fix_summary"], ensure_ascii=False, indent=4))
                    if vr.get("composition_feedback"):
                        prompt_parts.append(f"    Parent code generator refused to compose:")
                        prompt_parts.append(json.dumps(vr["composition_feedback"], ensure_ascii=False, indent=4))
                    if vr.get("structured_errors"):
                        prompt_parts.append(f"    Structured validation errors:")
                        prompt_parts.append(json.dumps(vr["structured_errors"], ensure_ascii=False, indent=4))
                if previous_errors.get("previous_errors"):
                    prompt_parts.append(f"  Errors:")
                    for err in previous_errors["previous_errors"]:
                        prompt_parts.append(f"    - {err}")
                prompt_parts.append(f"")
                prompt_parts.append(f"DIAGNOSIS: The previous decomposition did not compose cleanly.")
                prompt_parts.append(f"Repair the child boundaries and dataflow. Do not merely remove children unless they are truly unnecessary.")
                prompt_parts.append(f"Make sure every child input has a source and parent code can be implemented by child calls only.")
            else:
                prompt_parts.append(f"PREVIOUS DECOMPOSITION FAILED WITH THESE ERRORS:")
                for err in previous_errors:
                    prompt_parts.append(f"  - {err}")
                prompt_parts.append(f"Please fix these issues in your new decomposition.")

        prompt_parts.append(f"")
        prompt_parts.append(f"Maximum children allowed: {self.config.max_children}")
        prompt_parts.append(f"Maximum depth: {self.config.max_depth}")
        prompt_parts.append(f"Return ONLY the JSON response.")

        return "\n".join(prompt_parts)
    
    def _parse_response(self, content: str) -> Dict[str, Any]:
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```[a-zA-Z0-9]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
        
        # Trim trailing content after the last '}' to handle LLM extra text
        if "}" in content:
            last_brace = content.rfind("}")
            content = content[:last_brace + 1]
        
        # Normalize Python string prefixes (f"..." → "...") that LLM may output in JSON values
        content = re.sub(r'(?<=[\s:,\[{])[fFrRuUbB]+(")', r'\1', content)

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            print(f"Content preview: {content[:500]}")
            # Save raw content for debugging
            debug_dir = os.path.join(self.config.output_dir, "debug")
            os.makedirs(debug_dir, exist_ok=True)
            debug_path = os.path.join(debug_dir, f"decomposer_failed_{len(os.listdir(debug_dir)) if os.path.exists(debug_dir) else 0}.json")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Raw LLM response saved to: {debug_path}")
            return {"children": [], "error": str(e)}
    
    def _create_child_contract(self, child_data: Dict[str, Any]) -> ChildContract:
        return ChildContract(
            purpose=child_data.get("purpose", ""),
            inputs=[InputParam.from_dict(i) for i in child_data.get("inputs", [])],
            outputs=[OutputParam.from_dict(o) for o in child_data.get("outputs", [])],
            behavior=child_data.get("behavior", ""),
            signature=child_data.get("signature", ""),
            preconditions=child_data.get("preconditions", []),
            postconditions=child_data.get("postconditions", []),
            data_operations=[DataOperation.from_dict(op) for op in child_data.get("data_operations", [])]
        )
    
    def _create_child_node(
        self, 
        child_data: Dict[str, Any], 
        parent: Node, 
        child_index: int
    ) -> Node:
        child_name = child_data.get("name", f"child_{child_index}")
        node_id = f"{parent.node_id}_{child_index}"
        
        node = Node(
            node_id=node_id,
            name=child_name,
            depth=parent.depth + 1,
            parent_id=parent.node_id,
            purpose=child_data.get("purpose", ""),
            inputs=[InputParam.from_dict(i) for i in child_data.get("inputs", [])],
            outputs=[OutputParam.from_dict(o) for o in child_data.get("outputs", [])],
            boundary=Boundary.from_dict(child_data.get("boundary", {})),
            global_vars=[GlobalVar.from_dict(g) for g in child_data.get("global_vars", [])],
            preconditions=child_data.get("preconditions", []),
            postconditions=child_data.get("postconditions", []),
            stop_decompose=child_data.get("stop_decompose", False),
            stop_reason=child_data.get("stop_reason", ""),
            estimated_lines=child_data.get("estimated_lines", 0),
            requested_capabilities=child_data.get("requested_capabilities", [])
        )

        subprd_data = child_data.get("subprd", child_data)
        task_id = child_data.get("traceability", {}).get("derived_from", parent.node_id)
        subprd = SubPRD(
            task_id=f"{task_id}.{child_name}",
            purpose=child_data.get("purpose", ""),
            description=child_data.get("behavior", ""),
            inputs=[InputParam.from_dict(i) for i in child_data.get("inputs", [])],
            outputs=[OutputParam.from_dict(o) for o in child_data.get("outputs", [])],
            boundary=Boundary.from_dict(child_data.get("boundary", {})),
            constraints=child_data.get("constraints", []),
            acceptance_criteria=[AcceptanceCriterion.from_dict(ac) for ac in child_data.get("acceptance_criteria", [])],
            traceability=Traceability.from_dict(child_data.get("traceability", {})),
            dependencies=child_data.get("dependencies", [])
        )
        node.subprd = subprd

        # Inherit parent's data_sources so downstream decomposition can reference them
        if not node.data_sources and parent.data_sources:
            node.data_sources = parent.data_sources

        return node
    
    def _should_stop_decomposition(self, node: Node, child_data: Dict[str, Any]) -> Tuple[bool, str]:
        if node.depth >= self.config.max_depth:
            return True, f"Reached max depth {self.config.max_depth}"
        
        if child_data.get("stop_decompose", False):
            return True, child_data.get("stop_reason", "Marked as stop")
        
        estimated_lines = child_data.get("estimated_lines", 0)
        if estimated_lines > 0 and estimated_lines <= self.config.max_lines_threshold:
            return True, f"Estimated {estimated_lines} lines (threshold: {self.config.max_lines_threshold})"
        
        return False, ""
    
    def decompose(
        self, 
        node: Node, 
        previous_errors: Any = None,
        interface_plan_summary: str = ""
    ) -> Tuple[Node, List[str]]:
        """
        Decompose a node into child nodes.
        Returns (updated_node, errors).
        If errors is non-empty, decomposition failed.
        """
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": self._build_user_prompt(node, previous_errors, interface_plan_summary)}
        ]
        
        try:
            response = self.api_client.chat(messages, max_tokens=16384)
            self.last_response = response
        except Exception as e:
            return node, [f"API call failed: {e}"]
        
        parsed = self._parse_response(response)
        
        if "error" in parsed:
            return node, [f"Failed to parse LLM response: {parsed['error']}"]
        
        children_data = parsed.get("children", [])

        if not children_data:
            node.stop_decompose = True
            node.stop_reason = "No children returned - treating as leaf node"
            return node, []
        
        children = []
        children_contracts = {}
        errors = []
        
        for i, child_data in enumerate(children_data[:self.config.max_children]):
            child_node = self._create_child_node(child_data, node, i)
            
            should_stop, stop_reason = self._should_stop_decomposition(node, child_data)
            child_node.stop_decompose = should_stop
            child_node.stop_reason = stop_reason
            
            children.append(child_node)
            children_contracts[child_node.name] = self._create_child_contract(child_data)
        
        if len(children_data) > self.config.max_children:
            print(f"  [warning] Truncated children from {len(children_data)} to {self.config.max_children}")
            errors.append(f"Truncated children from {len(children_data)} to {self.config.max_children}")
        
        node.children = children
        node.children_contracts = children_contracts

        if parsed.get("data_sources"):
            node.data_sources = [DataSource.from_dict(ds) for ds in parsed.get("data_sources", [])]

        if parsed.get("dataflow_edges"):
            node.dataflow_edges = [DataflowEdge.from_dict(e) for e in parsed.get("dataflow_edges", [])]

        node.decomposition_rationale = parsed.get("decomposition_rationale", "")

        return node, errors

    def decompose_with_messages(
        self,
        node: Node,
        messages: List[Dict[str, str]]
    ) -> Tuple[Node, List[str]]:
        """
        Decompose using a pre-built messages array (for multi-turn conversation).
        Returns (updated_node, errors).
        """
        try:
            response = self.api_client.chat(messages, max_tokens=16384)
            self.last_response = response
        except Exception as e:
            return node, [f"API call failed: {e}"]

        parsed = self._parse_response(response)

        if "error" in parsed:
            return node, [f"Failed to parse LLM response: {parsed['error']}"]

        children_data = parsed.get("children", [])

        if not children_data:
            node.stop_decompose = True
            node.stop_reason = "No children returned - treating as leaf node"
            return node, []

        children = []
        children_contracts = {}
        errors = []

        for i, child_data in enumerate(children_data[:self.config.max_children]):
            child_node = self._create_child_node(child_data, node, i)

            should_stop, stop_reason = self._should_stop_decomposition(node, child_data)
            child_node.stop_decompose = should_stop
            child_node.stop_reason = stop_reason

            children.append(child_node)
            children_contracts[child_node.name] = self._create_child_contract(child_data)

        if len(children_data) > self.config.max_children:
            print(f"  [warning] Truncated children from {len(children_data)} to {self.config.max_children}")
            errors.append(f"Truncated children from {len(children_data)} to {self.config.max_children}")

        node.children = children
        node.children_contracts = children_contracts

        if parsed.get("data_sources"):
            node.data_sources = [DataSource.from_dict(ds) for ds in parsed.get("data_sources", [])]

        if parsed.get("dataflow_edges"):
            node.dataflow_edges = [DataflowEdge.from_dict(e) for e in parsed.get("dataflow_edges", [])]

        node.decomposition_rationale = parsed.get("decomposition_rationale", "")

        return node, errors

    # ========================================================================
    # Three-Stage Decomposition orchestration
    # ========================================================================

    def _build_children_from_parsed(
        self,
        node: Node,
        parsed: Dict[str, Any]
    ) -> Tuple[Node, List[str]]:
        """Build child nodes and contracts from parsed LLM JSON (shared by all decompose paths)."""
        children_data = parsed.get("children", [])

        if not children_data:
            node.stop_decompose = True
            node.stop_reason = "No children returned - treating as leaf node"
            return node, []

        children = []
        children_contracts = {}
        errors = []

        for i, child_data in enumerate(children_data[:self.config.max_children]):
            child_node = self._create_child_node(child_data, node, i)

            should_stop, stop_reason = self._should_stop_decomposition(node, child_data)
            child_node.stop_decompose = should_stop
            child_node.stop_reason = stop_reason

            children.append(child_node)
            children_contracts[child_node.name] = self._create_child_contract(child_data)

        if len(children_data) > self.config.max_children:
            print(f"  [warning] Truncated children from {len(children_data)} to {self.config.max_children}")
            errors.append(f"Truncated children from {len(children_data)} to {self.config.max_children}")

        node.children = children
        node.children_contracts = children_contracts

        if parsed.get("data_sources"):
            node.data_sources = [DataSource.from_dict(ds) for ds in parsed.get("data_sources", [])]

        if parsed.get("dataflow_edges"):
            node.dataflow_edges = [DataflowEdge.from_dict(e) for e in parsed.get("dataflow_edges", [])]

        node.decomposition_rationale = parsed.get("decomposition_rationale", "")

        return node, errors

    def _merge_staged_outputs(
        self,
        stage1: Dict[str, Any],
        stage2: Dict[str, Any],
        stage3: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge three stage outputs into a unified children list.

        Stage 1 is authoritative for: name, purpose, behavior, boundary, semantic_inputs,
          semantic_outputs, preconditions, postconditions, guarantees, composition_role.
        Stage 2 is authoritative for: inputs, outputs, signature, dataflow_edges,
          interface_preservation.
        Stage 3 is authoritative for: global_vars, data_operations, requested_capabilities,
          constraints, acceptance_criteria, traceability, node_type, stop_decompose, stop_reason.
        """
        s1_children = {c.get("name", ""): c for c in stage1.get("children", [])}
        s2_children = {c.get("name", ""): c for c in stage2.get("children", [])}
        s3_children = {c.get("name", ""): c for c in stage3.get("children", [])}

        s1_names = set(s1_children.keys())
        s3_names = set(s3_children.keys())

        # Validate child list consistency (best-effort, log warnings)
        if s1_names != s3_names:
            only_s1 = s1_names - s3_names
            only_s3 = s3_names - s1_names
            if only_s1:
                print(f"  [merge] Stage 1 has children missing from Stage 3: {only_s1}")
            if only_s3:
                print(f"  [merge] Stage 3 has children not in Stage 1: {only_s3}")

        merged = []
        for name in s1_children:
            m = {}

            # Stage 1 — structure fields (authoritative)
            s1 = s1_children[name]
            for key in ("name", "purpose", "behavior", "boundary", "semantic_inputs",
                        "semantic_outputs", "preconditions", "postconditions", "guarantees",
                        "composition_role"):
                if key in s1:
                    m[key] = s1[key]

            # Stage 2 — interface fields
            if name in s2_children:
                s2 = s2_children[name]
                for key in ("inputs", "outputs", "signature"):
                    if key in s2:
                        m[key] = s2[key]

            # Stage 3 — resource + governance fields
            if name in s3_children:
                s3 = s3_children[name]
                for key in ("global_vars", "data_operations", "requested_capabilities",
                            "constraints", "acceptance_criteria", "traceability",
                            "node_type", "stop_decompose", "stop_reason"):
                    if key in s3:
                        m[key] = s3[key]
                # Fallback for stop fields if not in Stage 3
                if "stop_decompose" not in m and "stop_decompose" in s1:
                    m["stop_decompose"] = s1["stop_decompose"]
                if "stop_reason" not in m and "stop_reason" in s1:
                    m["stop_reason"] = s1.get("stop_reason", "")

            # Ensure stop_decompose always has a value
            if "stop_decompose" not in m:
                m["stop_decompose"] = False
            if "stop_reason" not in m:
                m["stop_reason"] = ""

            merged.append(m)

        # Build the final output dict compatible with _build_children_from_parsed
        # Take data_sources from Stage 1 or Stage 2
        result: Dict[str, Any] = {"children": merged}

        if stage2.get("data_sources") or stage1.get("data_sources"):
            result["data_sources"] = stage2.get("data_sources") or stage1.get("data_sources", [])

        if stage2.get("dataflow_edges"):
            result["dataflow_edges"] = stage2["dataflow_edges"]
        elif stage1.get("dataflow_sketch"):
            # Convert dataflow_sketch to dataflow_edges as fallback
            result["dataflow_edges"] = [
                {
                    "from_node": e.get("from", "parent"),
                    "from_output": e.get("data", ""),
                    "to_node": e.get("to", "parent"),
                    "to_input": e.get("data", ""),
                    "note": e.get("note", ""),
                }
                for e in stage1["dataflow_sketch"]
            ]

        if stage2.get("decomposition_rationale") or stage1.get("decomposition_rationale"):
            result["decomposition_rationale"] = (
                stage2.get("decomposition_rationale") or
                stage1.get("decomposition_rationale", "")
            )

        if stage3.get("governance_notes"):
            result["governance_notes"] = stage3["governance_notes"]

        return result

    def _chat_and_parse(self, messages: List[Dict[str, str]], max_tokens: int = 16384) -> Dict[str, Any]:
        """Call API and parse the response. Returns parsed dict or dict with 'error' key."""
        try:
            response = self.api_client.chat(messages, max_tokens=max_tokens)
            self.last_response = response
        except Exception as e:
            return {"error": str(e)}

        parsed = self._parse_response(response)
        return parsed

    def decompose_staged(
        self,
        node: Node,
        previous_errors: Any = None,
        interface_plan_summary: str = ""
    ) -> Tuple[Node, List[str]]:
        """
        Three-stage decomposition using a single multi-turn conversation.

        Stage 1: structure only (name, purpose, behavior, boundary, etc.)
        Stage 2: interface derivation (inputs, outputs, signature, dataflow_edges)
        Stage 3: resource allocation (global_vars, data_operations, constraints, etc.)

        Returns (updated_node, errors).
        """
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": self._build_stage1_system_prompt()},
            {"role": "user", "content": self._build_stage1_user_prompt(node, previous_errors, interface_plan_summary)},
        ]

        # Stage 1: Structure — with retry for child count overflow
        max_s1_retries = self.config.max_decompose_retries
        stage1 = None
        for s1_attempt in range(max_s1_retries):
            stage1 = self._chat_and_parse(messages)
            if "error" in stage1:
                err_msg = stage1.get("error", "Stage 1 failed")
                if not stage1.get("children"):
                    return node, [f"Stage 1 parse failed: {err_msg}"]
            children_count = len(stage1.get("children", []))
            if children_count > self.config.max_children:
                if s1_attempt < max_s1_retries - 1:
                    print(f"  [staged] Stage 1 produced {children_count} children (max {self.config.max_children}), "
                          f"re-running Stage 1 with feedback (attempt {s1_attempt+2}/{max_s1_retries})")
                    messages.append({"role": "assistant", "content": json.dumps(stage1, ensure_ascii=False)})
                    messages.append({"role": "user", "content": (
                        f"You produced {children_count} children, exceeding the maximum of "
                        f"{self.config.max_children}. Please merge related responsibilities and "
                        f"re-decompose with at most {self.config.max_children} children. "
                        f"Children with similar purposes should be combined."
                    )})
                else:
                    print(f"  [staged] Stage 1 child count overflow ({children_count} > {self.config.max_children}) "
                          f"after {max_s1_retries} attempts, will truncate")
                    break
            else:
                break
        messages.append({"role": "assistant", "content": json.dumps(stage1, ensure_ascii=False)})

        # Stage 2: Interface derivation
        messages.append({"role": "system", "content": self._build_stage2_system_prompt()})
        messages.append({"role": "user", "content": self._build_stage2_user_prompt(node, stage1, previous_errors)})
        stage2 = self._chat_and_parse(messages)
        if "error" in stage2:
            err_msg = stage2.get("error", "Stage 2 failed")
            if not stage2.get("children"):
                print(f"  [staged] Stage 2 parse failed: {err_msg}, trying to proceed with Stage 1 + partial Stage 2")
        messages.append({"role": "assistant", "content": json.dumps(stage2, ensure_ascii=False)})

        # Stage 3: Resource allocation
        messages.append({"role": "system", "content": self._build_stage3_system_prompt()})
        messages.append({"role": "user", "content": self._build_stage3_user_prompt(node, stage1, stage2, previous_errors)})
        stage3 = self._chat_and_parse(messages)
        if "error" in stage3:
            err_msg = stage3.get("error", "Stage 3 failed")
            if not stage3.get("children"):
                print(f"  [staged] Stage 3 parse failed: {err_msg}, trying to proceed with Stage 1+2")
        messages.append({"role": "assistant", "content": json.dumps(stage3, ensure_ascii=False)})

        # Save full message history on node for potential re-decomposition
        node._staged_messages = messages

        # Merge stages
        merged = self._merge_staged_outputs(stage1, stage2, stage3)

        # Build children from merged output
        return self._build_children_from_parsed(node, merged)

    def decompose_staged_with_history(
        self,
        node: Node,
        previous_errors: Any = None,
        message_history: Optional[List[Dict[str, str]]] = None,
        interface_plan_summary: str = ""
    ) -> Tuple[Node, List[str]]:
        """
        Re-decompose using a three-stage conversation, starting from full message history.

        If message_history is provided (from a previous decompose_staged call), the LLM
        sees its full prior output plus error feedback, then regenerates all three stages
        from Stage 1.

        Returns (updated_node, errors).
        """
        if message_history:
            # Use existing history and append feedback
            messages = list(message_history)
            if previous_errors:
                fb = self._format_previous_errors(previous_errors)
                messages.append({
                    "role": "user",
                    "content": f"=== RE-DECOMPOSITION REQUESTED ===\n\n{fb}\n\nPlease re-decompose from Stage 1. Fix the issues identified above.",
                })
        else:
            # Fresh start with feedback in Stage 1
            return self.decompose_staged(node, previous_errors, interface_plan_summary)

        # Stage 1 — with full history context
        messages.append({"role": "system", "content": self._build_stage1_system_prompt()})
        stage1 = self._chat_and_parse(messages)
        if "error" in stage1 and not stage1.get("children"):
            return node, [f"Stage 1 re-decomposition failed: {stage1.get('error', 'unknown')}"]
        messages.append({"role": "assistant", "content": json.dumps(stage1, ensure_ascii=False)})

        # Stage 2
        messages.append({"role": "system", "content": self._build_stage2_system_prompt()})
        messages.append({"role": "user", "content": self._build_stage2_user_prompt(node, stage1, None)})
        stage2 = self._chat_and_parse(messages)
        if "error" in stage2 and not stage2.get("children"):
            print(f"  [staged-history] Stage 2 parse failed, proceeding with partial data")
        messages.append({"role": "assistant", "content": json.dumps(stage2, ensure_ascii=False)})

        # Stage 3
        messages.append({"role": "system", "content": self._build_stage3_system_prompt()})
        messages.append({"role": "user", "content": self._build_stage3_user_prompt(node, stage1, stage2, None)})
        stage3 = self._chat_and_parse(messages)
        if "error" in stage3 and not stage3.get("children"):
            print(f"  [staged-history] Stage 3 parse failed, proceeding with partial data")
        messages.append({"role": "assistant", "content": json.dumps(stage3, ensure_ascii=False)})

        # Save updated message history
        node._staged_messages = messages

        # Merge and build
        merged = self._merge_staged_outputs(stage1, stage2, stage3)
        return self._build_children_from_parsed(node, merged)

    def decompose_with_retry(
        self, 
        node: Node, 
        max_retries: int = None,
        previous_errors: Any = None,
        interface_plan_summary: str = ""
    ) -> Tuple[Node, List[str]]:
        """
        Decompose with retry on failure.
        """
        retries = max_retries if max_retries is not None else self.config.max_decompose_retries
        all_errors = []
        
        for attempt in range(retries):
            context_errors = previous_errors if attempt == 0 and previous_errors else (all_errors if attempt > 0 else None)
            node, errors = self.decompose(node, context_errors, interface_plan_summary)
            
            if not errors:
                return node, []
            
            all_errors = errors
            print(f"Decomposition attempt {attempt + 1} failed: {errors}")
        
        return node, all_errors
