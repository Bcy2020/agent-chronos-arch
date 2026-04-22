"""
Decomposer LLM: Decomposes a node into child nodes.
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from config import Config
from api_client import APIClient
from models import Node, InputParam, OutputParam, Boundary, GlobalVar, ChildContract, DataSource, DataOperation


class Decomposer:
    def __init__(self, config: Config, api_client: APIClient):
        self.config = config
        self.api_client = api_client

    def _build_system_prompt(self) -> str:
        return """You are a software system decomposition agent. Your task is to decompose a function block into smaller child function blocks.

CRITICAL OUTPUT LANGUAGE RULE: All descriptive content (purpose, behavior, descriptions, decomposition_rationale, etc.) MUST be in Chinese. Only code-related identifiers (function names, variable names, type names) should be in English.

CRITICAL RULES - ENFORCED:
1. EVERY CHILD MUST BE A FUNCTION, NOT A CLASS. Never generate class definitions for child blocks.
2. Each child must have explicit: name, purpose, inputs, outputs, and boundary
3. Preserve the parent's external interface - children's composition must match parent's inputs/outputs
4. Do NOT introduce hidden coordinators, routers, or aggregators - if coordination is needed, create an explicit child
5. Do NOT add extra external inputs or outputs beyond what the parent has
6. Children should be at the same abstraction level and minimally overlapping

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
      "purpose": "这个子函数的具体用途描述（用中文）",
      "inputs": [{"name": "param", "type": "str", "description": "参数描述（用中文）"}],
      "outputs": [{"name": "result", "type": "int", "description": "返回值描述（用中文）"}],
      "boundary": {"in_scope": ["..."], "out_of_scope": ["..."]},
      "preconditions": ["..."],
      "postconditions": ["..."],
      "behavior": "详细描述这个函数如何将输入转换为输出，包括具体的处理逻辑（用中文）",
      "signature": "def ChildName(param1: type1, param2: type2) -> return_type",
      "stop_decompose": false,
      "stop_reason": "",
      "node_type": "coordination|pure_function|atomic_operation",
      "data_operations": [
        {"source_name": "data_source_name", "operation_type": "read|write|read_write", "description": "执行的具体操作描述（用中文）"}
      ]
    }
  ],
  "data_sources": [
    {"name": "source_name", "category": "database|file|cache|external|memory", "access": "read|write|read_write", "data_type": "dict|list|object", "description": "数据源描述（用中文）"}
  ],
  "global_vars": [
    {"name": "var_name", "type": "Type", "access": "read|read_write", "description": "变量描述（用中文）", "data_source": "source_name", "data_type": "dict", "operations": ["read"]}
  ],
  "decomposition_rationale": "关键说明：解释这些子函数如何协作来实现父函数的功能。描述数据流向、处理流程，以及它们如何共同覆盖父节点的所有职责（用中文）",
  "interface_preservation": {
    "parent_inputs_covered_by": {"input_name": "child_name"},
    "parent_outputs_produced_by": {"output_name": "child_name"}
  }
}"""

    def _build_user_prompt(self, node: Node, previous_errors: List[str] = None) -> str:
        prompt_parts = [
            f"Decompose the following function block:",
            f"",
            f"Node Name: {node.name}",
            f"Node Purpose: {node.purpose}",
            f"",
            f"Inputs:",
        ]

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

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            print(f"Content preview: {content[:500]}")
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

        return Node(
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
            response = self.api_client.chat(messages)
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
        max_retries: int = None
    ) -> Tuple[Node, List[str]]:
        """
        Decompose with retry on failure.
        """
        retries = max_retries if max_retries is not None else self.config.max_decompose_retries
        all_errors = []

        for attempt in range(retries):
            node, errors = self.decompose(node, all_errors if attempt > 0 else None)

            if not errors:
                return node, []

            all_errors = errors
            print(f"Decomposition attempt {attempt + 1} failed: {errors}")

        return node, all_errors
