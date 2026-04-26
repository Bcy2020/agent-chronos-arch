"""
Decomposer LLM: Decomposes a node into child nodes.
"""
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from config import Config
from api_client import APIClient
from models import Node, InputParam, OutputParam, Boundary, GlobalVar, ChildContract, DataSource, DataOperation, SubPRD, Traceability, StateOperation, AcceptanceCriterion


class Decomposer:
    def __init__(self, config: Config, api_client: APIClient):
        self.config = config
        self.api_client = api_client
    
    def _build_system_prompt(self) -> str:
        return """You are a software system decomposition agent. Your task is to decompose a function block into smaller child function blocks.

CRITICAL RULES - ENFORCED:
1. EVERY CHILD MUST BE A FUNCTION, NOT A CLASS. Never generate class definitions for child blocks.
2. Each child must have explicit: name, purpose, inputs, outputs, and boundary
3. Preserve the parent's external interface - children's composition must match parent's inputs/outputs
4. Do NOT introduce hidden coordinators, routers, or aggregators - if coordination is needed, create an explicit child
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
      "node_type": "coordination|pure_function|atomic_operation",
      "data_operations": [
        {"source_name": "data_source_name", "operation_type": "read|write|read_write", "description": "what operation is performed"}
      ],
      "constraints": [{"constraint_id": "C-001", "description": "constraint description"}],
      "acceptance_criteria": [{"ac_id": "AC-001", "description": "criterion description", "verification_method": "automated_test"}],
      "global_state_operations": [
        {
          "op_id": "op_001", "source_id": "data_store_name",
          "op_type": "read|write|read_then_write|delete",
          "target": {"item_path": "root", "condition": ""},
          "payload": {"fields": ["field1"], "new_value": "description"},
          "constraint": "unique_id_generation",
          "depends_on": ""
        }
      ],
      "traceability": {"parent_requirement_ids": ["FR-001"], "derived_from": "root"}
    }
  ],
  "data_sources": [
    {"name": "source_name", "category": "database|file|cache|external|memory", "access": "read|write|read_write", "data_type": "dict|list|object", "description": "description"}
  ],
  "global_vars": [
    {"name": "var_name", "type": "Type", "access": "read|read_write", "description": "desc", "data_source": "source_name", "data_type": "dict", "operations": ["read"]}
  ],
  "decomposition_rationale": "CRITICAL: Explain HOW these children work together to implement the parent. Describe the interaction flow, data transformation, and how they collectively cover ALL parent responsibilities. This is required for the code generator to understand how to compose these functions.",
  "interface_preservation": {
    "parent_inputs_covered_by": {"input_name": "child_name"},
    "parent_outputs_produced_by": {"output_name": "child_name"}
  },
  "global_ops_distribution": {
    "rationale": "Explain how each of the parent's global_state_operations is distributed to which children",
    "parent_op_to_child_mapping": {"parent_op_id": "child_name"}
  }
}

CRITICAL GLOBAL STATE DISTRIBUTION RULE:
When the parent has "global_state_operations", each declared operation MUST be claimed by one or more children:
- A child that reads/writes a data source declares its own "global_state_operations" matching the parent's
- A coordinator child should NOT claim data operations - it delegates to children that actually perform them
- If you mark "global_ops_distribution", the code generator will use it to verify proper delegation"""
    
    def _build_user_prompt(self, node: Node, previous_errors: List[str] = None) -> str:
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
            if node.subprd.global_state_operations:
                prompt_parts.append(f"  Global State Operations:")
                for op in node.subprd.global_state_operations:
                    prompt_parts.append(f"    - {op.op_id}: {op.op_type} on {op.source_id}")
            if node.subprd.traceability.parent_requirement_ids:
                prompt_parts.append(f"  Traces to: {', '.join(node.subprd.traceability.parent_requirement_ids)}")
            if node.subprd.global_state_operations:
                prompt_parts.append(f"")
                prompt_parts.append(f"  >>> The Global State Operations listed above must be DISTRIBUTED to children. <<<")
                prompt_parts.append(f"  Each child that directly uses a data source must declare its own global_state_operations.")
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
            prompt_parts.append(f"Global Variables:")
            for gv in node.global_vars:
                access = "READ-ONLY" if gv.access == "read" else "READ-WRITE"
                prompt_parts.append(f"  - {gv.name}: {gv.type} ({access}) - {gv.description}")
                if gv.data_source:
                    prompt_parts.append(f"    Data Source: {gv.data_source}")

        if node.preconditions:
            prompt_parts.append(f"Preconditions: {node.preconditions}")
        if node.postconditions:
            prompt_parts.append(f"Postconditions: {node.postconditions}")

        if previous_errors:
            prompt_parts.append(f"")
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
            estimated_lines=child_data.get("estimated_lines", 0)
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
            global_state_operations=[StateOperation.from_dict(op) for op in child_data.get("global_state_operations", [])],
            dependencies=child_data.get("dependencies", [])
        )
        node.subprd = subprd

        # Inherit parent's data_sources so downstream decomposition can reference them
        if not node.data_sources and parent.data_sources:
            node.data_sources = parent.data_sources
        if not node.global_vars and parent.global_vars:
            node.global_vars = parent.global_vars

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
        previous_errors: List[str] = None
    ) -> Tuple[Node, List[str]]:
        """
        Decompose a node into child nodes.
        Returns (updated_node, errors).
        If errors is non-empty, decomposition failed.
        """
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": self._build_user_prompt(node, previous_errors)}
        ]
        
        try:
            response = self.api_client.chat(messages, max_tokens=16384)
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
            errors.append(f"Truncated children from {len(children_data)} to {self.config.max_children}")
        
        node.children = children
        node.children_contracts = children_contracts

        if parsed.get("global_vars"):
            node.global_vars = [GlobalVar.from_dict(g) for g in parsed.get("global_vars", [])]

        if parsed.get("data_sources"):
            node.data_sources = [DataSource.from_dict(ds) for ds in parsed.get("data_sources", [])]

        node.decomposition_rationale = parsed.get("decomposition_rationale", "")

        return node, errors
    
    def decompose_with_retry(
        self, 
        node: Node, 
        max_retries: int = None,
        previous_errors: List[str] = None
    ) -> Tuple[Node, List[str]]:
        """
        Decompose with retry on failure.
        """
        retries = max_retries if max_retries is not None else self.config.max_decompose_retries
        all_errors = []
        
        for attempt in range(retries):
            context_errors = previous_errors if attempt == 0 and previous_errors else (all_errors if attempt > 0 else None)
            node, errors = self.decompose(node, context_errors)
            
            if not errors:
                return node, []
            
            all_errors = errors
            print(f"Decomposition attempt {attempt + 1} failed: {errors}")
        
        return node, all_errors
