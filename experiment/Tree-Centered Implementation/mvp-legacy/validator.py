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
    
    def validate(self, node: Node, code: str) -> ValidationResult:
        """
        Run all validations on the generated code.
        """
        all_errors = []
        
        syntax_ok, syntax_errors = self.validate_syntax(code)
        all_errors.extend(syntax_errors)
        
        if syntax_ok:
            interface_ok, interface_errors = self.validate_interface_preservation(node, code)
            all_errors.extend(interface_errors)
            
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
            if "Missing parameters" in error:
                return True
            if "Function name mismatch" in error:
                return True
        
        return False
