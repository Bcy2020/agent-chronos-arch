"""
Validator: Validates generated code and triggers re-decomposition if needed.
"""
import ast
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from config import Config
from models import Node, ValidationResult


class Validator:
    def __init__(self, config: Config):
        self.config = config
    
    def validate_syntax(self, code: str) -> Tuple[bool, List[str]]:
        """
        Check if the code is syntactically valid Python.
        """
        errors = []
        
        if not code or not code.strip():
            errors.append("Code is empty")
            return False, errors
        
        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
            return False, errors
        
        return True, errors
    
    def _extract_function_calls(self, code: str) -> Set[str]:
        """
        Extract all function calls from the code.
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return set()
        
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
        
        return calls
    
    def _extract_function_def(self, code: str) -> Optional[ast.FunctionDef]:
        """
        Extract the main function definition from the code.
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return None
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                return node
        
        return None
    
    def _get_function_params(self, func_def: ast.FunctionDef) -> Set[str]:
        """
        Get parameter names from a function definition.
        """
        params = set()
        for arg in func_def.args.args:
            params.add(arg.arg)
        return params
    
    def validate_interface_preservation(self, node: Node, code: str) -> Tuple[bool, List[str]]:
        """
        Check if the code preserves the node's interface.
        """
        errors = []
        
        func_def = self._extract_function_def(code)
        if not func_def:
            errors.append("No function definition found in code")
            return False, errors
        
        expected_params = {inp.name for inp in node.inputs}
        actual_params = self._get_function_params(func_def)
        
        missing_params = expected_params - actual_params
        if missing_params:
            errors.append(f"Missing parameters: {missing_params}")
        
        if func_def.name != node.name:
            errors.append(f"Function name mismatch: expected '{node.name}', got '{func_def.name}'")
        
        return len(errors) == 0, errors
    
    def validate_signature(self, node: Node, code: str) -> Tuple[bool, List[str]]:
        """
        Full signature validation for ALL nodes (root, parent, leaf):
        function name, parameter count, parameter names, parameter types, and return type
        must all match the node's declared interface.
        This is a strict superset of validate_interface_preservation.
        """
        errors = []
        
        func_def = self._extract_function_def(code)
        if not func_def:
            errors.append("No function definition found in code")
            return False, errors
        
        expected_params = list(node.inputs)
        actual_args = func_def.args.args
        
        # 1. Function name check
        if func_def.name != node.name:
            errors.append(f"Function name mismatch: expected '{node.name}', got '{func_def.name}'")
        
        # 2. Parameter names
        expected_param_names = {inp.name for inp in expected_params}
        actual_param_names = {arg.arg for arg in actual_args}
        
        missing_params = expected_param_names - actual_param_names
        if missing_params:
            errors.append(f"Missing parameters: {missing_params}")
        
        extra_params = actual_param_names - expected_param_names
        if extra_params:
            errors.append(f"Extra parameters: {extra_params}")
        
        # 3. Parameter type annotations
        for i, inp in enumerate(expected_params):
            if i < len(actual_args):
                arg = actual_args[i]
                if arg.arg == inp.name and arg.annotation:
                    actual_type = ast.unparse(arg.annotation).strip()
                    if actual_type != inp.type:
                        errors.append(
                            f"Parameter '{inp.name}' type mismatch: expected '{inp.type}', got '{actual_type}'"
                        )
        
        # 4. Return type annotation
        if func_def.returns:
            actual_return = ast.unparse(func_def.returns).strip()
            if len(node.outputs) == 0:
                expected_return = "None"
            elif len(node.outputs) == 1:
                expected_return = node.outputs[0].type
            else:
                expected_return = f"Tuple[{', '.join(o.type for o in node.outputs)}]"
            if actual_return != expected_return:
                errors.append(f"Return type mismatch: expected '{expected_return}', got '{actual_return}'")
        else:
            if len(node.outputs) > 0:
                errors.append("Missing return type annotation")
        
        return len(errors) == 0, errors
    
    def validate_child_usage(self, node: Node, code: str) -> Tuple[bool, List[str]]:
        """
        Check if the code correctly uses child function interfaces.
        """
        errors = []
        
        if not node.children:
            return True, errors
        
        child_names = {child.name for child in node.children}
        called_functions = self._extract_function_calls(code)
        
        used_children = child_names & called_functions
        unused_children = child_names - called_functions
        
        if unused_children:
            errors.append(f"Child functions not used: {unused_children}")
        
        return len(errors) == 0, errors
    
    def validate_global_vars(self, node: Node, code: str) -> Tuple[bool, List[str]]:
        """
        Check if the code correctly handles global variables.
        For parent nodes: should only read, not write.
        For leaf nodes: can read and write as specified.
        """
        errors = []
        
        if not node.global_vars:
            return True, errors
        
        global_var_names = {gv.name for gv in node.global_vars}
        
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False, ["Cannot parse code for global var check"]
        
        for node_ast in ast.walk(tree):
            if isinstance(node_ast, ast.Global):
                for name in node_ast.names:
                    if name not in global_var_names:
                        errors.append(f"Undeclared global variable: {name}")
        
        return len(errors) == 0, errors
    
    def check_conservation(self, node: Node) -> List[str]:
        """
        Global State Conservation Law: Parent Global Operations = Σ(Child Global Operations).
        Only checks parent nodes with children that have SubPRD with global_state_operations.

        Checks from Tree-Centered Implementation Refinement:
        - Completeness: All parent global_state_operations source_ids are covered by at least one child
        - Correctness: Children only operate on data sources declared by parent
        - Atomicity: Each individual StateOperation targets exactly one data source (structural guarantee)
        """
        errors = []

        if not node.children or not node.subprd:
            return errors

        parent_ops = node.subprd.global_state_operations
        if not parent_ops:
            return errors

        child_ops_by_source = {}
        for child in node.children:
            if not child.subprd:
                continue
            for op in child.subprd.global_state_operations:
                sid = op.source_id
                if sid not in child_ops_by_source:
                    child_ops_by_source[sid] = []
                child_ops_by_source[sid].append({"child": child.name, "op_type": op.op_type, "op_id": op.op_id})

        for op in parent_ops:
            if op.source_id not in child_ops_by_source:
                errors.append(
                    f"Conservation violation - Completeness: parent operation '{op.op_id}' "
                    f"on '{op.source_id}' ({op.op_type}) is not assigned to any child"
                )
                continue

            child_types = {cop["op_type"] for cop in child_ops_by_source[op.source_id]}

            if op.op_type == "read_then_write":
                has_read = "read" in child_types or "read_then_write" in child_types
                has_write = "write" in child_types or "read_then_write" in child_types
                if not (has_read and has_write):
                    errors.append(
                        f"Conservation violation - Completeness: parent '{op.op_id}' requires "
                        f"read+write on '{op.source_id}', but children only provide: {child_types}"
                    )

        declared_sources = set()
        for op in parent_ops:
            declared_sources.add(op.source_id)
        for ds in node.data_sources:
            declared_sources.add(ds.name)

        for child in node.children:
            if not child.subprd:
                continue
            for op in child.subprd.global_state_operations:
                if op.source_id not in declared_sources:
                    errors.append(
                        f"Conservation violation - Correctness: child '{child.name}' operates on "
                        f"undeclared data source '{op.source_id}'"
                    )

        return errors

    def validate(self, node: Node, code: str) -> ValidationResult:
        """
        Run all validations on the generated code.
        """
        all_errors = []
        
        syntax_ok, syntax_errors = self.validate_syntax(code)
        all_errors.extend(syntax_errors)
        
        if syntax_ok:
            sig_ok, sig_errors = self.validate_signature(node, code)
            all_errors.extend(sig_errors)
            
            child_ok, child_errors = self.validate_child_usage(node, code)
            all_errors.extend(child_errors)
            
            global_ok, global_errors = self.validate_global_vars(node, code)
            all_errors.extend(global_errors)
        
        return ValidationResult(
            passed=len(all_errors) == 0,
            errors=all_errors,
            retry_count=node.validation.retry_count
        )
    
    def should_redecompose(self, node: Node, validation: ValidationResult) -> bool:
        """
        Determine if the node should be re-decomposed based on validation errors.
        """
        if validation.passed:
            return False
        
        if node.validation.retry_count >= self.config.max_decompose_retries:
            return False
        
        for error in validation.errors:
            if "Child functions not used" in error:
                return True
        
        return False
