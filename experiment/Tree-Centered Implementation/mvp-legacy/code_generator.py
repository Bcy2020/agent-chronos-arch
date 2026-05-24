"""
CodeGenerator LLM: Generates Python code for a node.
- For parent nodes: composes child node interfaces
- For leaf nodes: generates complete implementation
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from config import Config
from api_client import APIClient
from models import Node, ChildContract


class CodeGenerator:
    def __init__(self, config: Config, api_client: APIClient):
        self.config = config
        self.api_client = api_client
    
    def _build_system_prompt_for_parent(self) -> str:
        return """You are a Python code generator. Your task is to implement a function by composing its child functions.

CRITICAL RULES:
1. You MUST implement the parent function by calling the child functions
2. Child functions are NOT implemented yet - you only have their interfaces
3. Use the child function signatures exactly as provided
4. The parent function's inputs/outputs must match the specification
5. You may use: conditionals, loops, local variables, helper logic
6. DO NOT directly read or write global state - delegate ALL data operations to child functions
7. Parent function should only orchestrate child calls, not perform data operations

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
  "imports": ["import os", "from typing import ..."],
  "child_calls": ["child1", "child2"],
  "implementation_notes": "Brief explanation of the logic"
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
        previous_errors: List[str] = None
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
            lines.append(f"Data Sources (Available Data Stores):")
            for ds in node.data_sources:
                lines.append(f"  - {ds.name} ({ds.category}, {ds.access})")
                lines.append(f"    Type: {ds.data_type}")
                lines.append(f"    Description: {ds.description}")

        if node.global_vars:
            lines.append(f"")
            lines.append(f"Global Variables:")
            for gv in node.global_vars:
                access = "READ-ONLY" if gv.access == "read" else "READ-WRITE"
                lines.append(f"  - {gv.name}: {gv.type} ({access}) - {gv.description}")
                if gv.data_source:
                    lines.append(f"    Data Source: {gv.data_source}")
                    lines.append(f"    Operations: {', '.join(gv.operations)}")

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

        for child_name, contract in node.children_contracts.items():
            lines.append(f"")
            lines.append(f"  [{child_name}]")
            lines.append(f"    Purpose: {contract.purpose}")
            lines.append(f"    Behavior: {contract.behavior}")

            if contract.signature:
                lines.append(f"    Signature: {contract.signature}")
            else:
                inputs_str = ", ".join([f"{i.name}: {i.type}" for i in contract.inputs])
                outputs_str = ", ".join([o.type for o in contract.outputs]) if contract.outputs else "None"
                lines.append(f"    Signature: def {child_name}({inputs_str}) -> {outputs_str}")

            if contract.data_operations:
                lines.append(f"    Data Operations:")
                for op in contract.data_operations:
                    lines.append(f"      - {op.source_name}: {op.operation_type} ({op.description})")

            if contract.preconditions:
                lines.append(f"    Preconditions: {contract.preconditions}")
            if contract.postconditions:
                lines.append(f"    Postconditions: {contract.postconditions}")

        if node.global_vars:
            lines.append(f"")
            lines.append(f"Global Variables:")
            for gv in node.global_vars:
                access = "READ-ONLY" if gv.access == "read" else "READ-WRITE"
                lines.append(f"  - {gv.name}: {gv.type} ({access}) - {gv.description}")

        if previous_errors:
            lines.append(f"")
            lines.append(f"=" * 60)
            lines.append(f"PREVIOUS CODE GENERATION FAILED WITH THESE ERRORS:")
            lines.append(f"=" * 60)
            for err in previous_errors:
                lines.append(f"  - {err}")
            lines.append(f"Please fix these issues in your new code.")

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
    
    def _build_user_prompt_for_leaf(
        self, 
        node: Node, 
        previous_errors: List[str] = None
    ) -> str:
        lines = [
            f"Implement this function:",
            f"",
            f"Function: {node.name}",
            f"Purpose: {node.purpose}",
            f"",
            f"Inputs:",
        ]
        
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
                access = "READ-ONLY" if gv.access == "read" else "READ-WRITE"
                lines.append(f"  {gv.name}: {gv.type} ({access}) - {gv.description}")
                if gv.data_source:
                    lines.append(f"    Data Source: {gv.data_source}")
                    lines.append(f"    Data Type: {gv.data_type}")
                    lines.append(f"    Allowed Operations: {', '.join(gv.operations)}")

        if previous_errors:
            lines.append(f"")
            lines.append(f"PREVIOUS CODE GENERATION FAILED WITH THESE ERRORS:")
            for err in previous_errors:
                lines.append(f"  - {err}")
            lines.append(f"Please fix these issues in your new code.")
        
        lines.append(f"")
        lines.append(f"Generate a complete implementation.")
        
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
        previous_errors: List[str] = None
    ) -> Tuple[str, List[str]]:
        """
        Generate code for a parent node by composing child interfaces.
        Returns (code, errors).
        """
        if not node.children:
            return "", ["Cannot generate parent code: no children defined"]
        
        messages = [
            {"role": "system", "content": self._build_system_prompt_for_parent()},
            {"role": "user", "content": self._build_user_prompt_for_parent(node, previous_errors)}
        ]
        
        try:
            response = self.api_client.chat(messages, max_tokens=2048)
        except Exception as e:
            return "", [f"API call failed: {e}"]
        
        parsed = self._parse_response(response)
        
        if "error" in parsed or not parsed.get("code"):
            return "", [f"Failed to parse code: {parsed.get('error', 'No code generated')}"]
        
        return parsed.get("code", ""), []
    
    def generate_for_leaf(
        self, 
        node: Node, 
        previous_errors: List[str] = None
    ) -> Tuple[str, List[str]]:
        """
        Generate complete code for a leaf node.
        Returns (code, errors).
        """
        messages = [
            {"role": "system", "content": self._build_system_prompt_for_leaf()},
            {"role": "user", "content": self._build_user_prompt_for_leaf(node, previous_errors)}
        ]
        
        try:
            response = self.api_client.chat(messages, max_tokens=2048)
        except Exception as e:
            return "", [f"API call failed: {e}"]
        
        parsed = self._parse_response(response)
        
        if "error" in parsed or not parsed.get("code"):
            return "", [f"Failed to parse code: {parsed.get('error', 'No code generated')}"]
        
        return parsed.get("code", ""), []
    
    def generate(
        self, 
        node: Node, 
        previous_errors: List[str] = None
    ) -> Tuple[str, List[str]]:
        """
        Generate code for any node.
        Returns (code, errors).
        """
        if node.stop_decompose or not node.children:
            return self.generate_for_leaf(node, previous_errors)
        else:
            return self.generate_for_parent(node, previous_errors)
    
    def generate_with_retry(
        self, 
        node: Node, 
        max_retries: int = None
    ) -> Tuple[str, List[str]]:
        """
        Generate code with retry on failure.
        """
        retries = max_retries if max_retries is not None else self.config.max_decompose_retries
        all_errors = []
        
        for attempt in range(retries):
            code, errors = self.generate(node, all_errors if attempt > 0 else None)
            
            if not errors:
                return code, []
            
            all_errors = errors
            print(f"Code generation attempt {attempt + 1} failed: {errors}")
        
        return "", all_errors
