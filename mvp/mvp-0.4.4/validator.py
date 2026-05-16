"""
Validator: Validates generated code and triggers re-decomposition if needed.
"""
import ast
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from config import Config
from models import Node, ValidationResult, ValidationError, InterfacePlan


class Validator:
    def __init__(self, config: Config, interface_plan: InterfacePlan = None):
        self.config = config
        self.interface_plan = interface_plan
        self._resource_names = set()
        self._interface_functions = {}
        if interface_plan:
            self.set_interface_plan(interface_plan)

    def set_interface_plan(self, plan: InterfacePlan) -> None:
        self.interface_plan = plan
        self._resource_names = {r.resource_id for r in plan.resources}
        self._interface_functions = {i.interface_id: i.function_name for i in plan.interfaces}
    
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
        errors = []
        
        if not node.global_vars:
            return True, errors
        
        global_var_names = {gv.variable for gv in node.global_vars}
        
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

    def validate_no_direct_resource_access(self, node: Node, code: str) -> Tuple[bool, List[str]]:
        errors = []
        if not node.children:
            return True, errors

        resource_names = set(self._resource_names)
        resource_names |= {gv.variable for gv in node.global_vars}
        resource_names |= {ds.name for ds in node.data_sources}

        if not resource_names:
            return True, errors

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return True, errors

        for n in ast.walk(tree):
            if isinstance(n, ast.Name) and n.id in resource_names:
                errors.append(f"DIRECT_RESOURCE_ACCESS_PARENT: resource={n.id}")
            elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in resource_names:
                errors.append(f"DIRECT_RESOURCE_ACCESS_PARENT: resource={n.value.id} attr={n.attr}")
            elif isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id in resource_names:
                errors.append(f"DIRECT_RESOURCE_ACCESS_PARENT: resource={n.value.id} subscript")

        return len(errors) == 0, errors

    def validate_leaf_interface_usage(self, node: Node, code: str) -> Tuple[bool, List[str]]:
        errors = []
        if node.children:
            return True, errors
        if not node.granted_capabilities:
            return True, errors

        granted_ids = set(node.granted_capabilities.granted_interfaces)
        granted_funcs = {self._interface_functions[i] for i in granted_ids if i in self._interface_functions}
        all_interface_funcs = set(self._interface_functions.values())

        called = self._extract_function_calls(code)
        ungranted = (called & all_interface_funcs) - granted_funcs
        for fn in sorted(ungranted):
            errors.append(f"UNGRANTED_INTERFACE_CALL: function={fn}")

        if re.search(r"op_[a-zA-Z0-9_]+", code):
            errors.append("INTERFACE_USAGE_VIOLATION: op_id referenced in generated code")

        return len(errors) == 0, errors

    def validate_child_input_provenance(self, node: Node, code: str) -> Tuple[bool, List[str]]:
        errors = []
        if not node.children:
            return True, errors

        func = self._extract_function_def(code)
        if not func:
            return True, errors

        child_names = {c.name for c in node.children}
        available = {arg.arg for arg in func.args.args}

        def name_roots(expr):
            roots = set()
            for x in ast.walk(expr):
                if isinstance(x, ast.Name):
                    roots.add(x.id)
            return roots

        def assigned_names(target):
            if isinstance(target, ast.Name):
                return {target.id}
            if isinstance(target, (ast.Tuple, ast.List)):
                result = set()
                for elt in target.elts:
                    result |= assigned_names(elt)
                return result
            return set()

        def process_stmts(stmts, avail):
            """Process a list of statements recursively, updating avail in place."""
            for stmt in stmts:
                # For loops: add loop variable(s) before processing body
                if isinstance(stmt, ast.For):
                    avail |= assigned_names(stmt.target)
                    process_stmts(stmt.body, avail)
                    # Don't update avail from orelse/else at the same level;
                    # variables from else branch may not be defined
                    continue

                # Try: process body, except handlers, else, finally
                if isinstance(stmt, ast.Try):
                    process_stmts(stmt.body, avail)
                    for handler in stmt.handlers:
                        if handler.type is None and handler.name is None:
                            pass  # bare except: don't add any var
                        elif handler.name:
                            avail.add(handler.name)
                        process_stmts(handler.body, avail)
                    if stmt.orelse:
                        process_stmts(stmt.orelse, avail)
                    if stmt.finalbody:
                        process_stmts(stmt.finalbody, avail)
                    continue

                # If/elif/else: process all branches (conservative: don't cross-pollinate)
                if isinstance(stmt, ast.If):
                    process_stmts(stmt.body, avail)
                    if stmt.orelse:
                        process_stmts(stmt.orelse, avail)
                    continue

                # With statement: add any binding names, process body
                if isinstance(stmt, ast.With):
                    for item in stmt.items:
                        if item.optional_vars:
                            avail |= assigned_names(item.optional_vars)
                    process_stmts(stmt.body, avail)
                    continue

                # Check ALL calls in this statement (including nested in sub-expressions)
                calls = [x for x in ast.walk(stmt) if isinstance(x, ast.Call)]
                for call in calls:
                    if isinstance(call.func, ast.Name) and call.func.id in child_names:
                        child_name = call.func.id
                        for arg in call.args:
                            for root in name_roots(arg):
                                if root in child_names:
                                    continue
                                if root not in avail:
                                    errors.append(
                                        f"CHILD_INPUT_SOURCE_MISSING: child={child_name} arg={root} available={sorted(avail)}"
                                    )

                # Update available from assignments
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        avail |= assigned_names(target)
                elif isinstance(stmt, ast.AnnAssign):
                    avail |= assigned_names(stmt.target)
                elif isinstance(stmt, ast.AugAssign):
                    avail |= assigned_names(stmt.target)

        process_stmts(func.body, available)
        return len(errors) == 0, errors

    def _decide_repair_action(self, structured_errors: List[ValidationError], node: Node) -> str:
        if not structured_errors:
            return "retry_code"

        structural = {
            "UNUSED_CHILD",
            "CANNOT_COMPOSE",
            "CHILD_INPUT_SOURCE_MISSING",
            "DIRECT_RESOURCE_ACCESS_PARENT",
            "CONSERVATION_VIOLATION",
        }

        if any(e.error_type in structural for e in structured_errors):
            return "redecompose"

        if any(e.error_type == "UNKNOWN" for e in structured_errors):
            return "retry_code"

        return "retry_code"

    def _build_fix_summary(self, structured_errors: List[ValidationError]) -> Dict[str, Any]:
        return {
            "error_types": [e.error_type for e in structured_errors],
            "missing_child_inputs": [e.details for e in structured_errors if e.error_type == "CHILD_INPUT_SOURCE_MISSING"],
            "direct_resource_accesses": [e.message for e in structured_errors if e.error_type == "DIRECT_RESOURCE_ACCESS_PARENT"],
            "suggestion": "If repair_action is redecompose, add/rewrite child boundaries so every child input has a source and parent does not access resources directly."
        }

    def check_conservation(self, node: Node) -> List[str]:
        """
        Global State Conservation Law: Parent Global Variables ⊇ Σ(Child Global Variables).
        
        - Completeness: Every parent global_var's variable+op combination must be covered
          by at least one child's global_vars.
        - Correctness: Children only declare global_vars that are subsets of parent's.
        """
        errors = []

        if not node.children:
            return errors

        parent_gvs = node.global_vars
        if not parent_gvs:
            return errors

        child_gvs_by_variable = {}
        for child in node.children:
            for gv in child.global_vars:
                if gv.variable not in child_gvs_by_variable:
                    child_gvs_by_variable[gv.variable] = []
                child_gvs_by_variable[gv.variable].append({"child": child.name, "op": gv.op})

        for gv in parent_gvs:
            if gv.variable not in child_gvs_by_variable:
                errors.append(
                    f"Conservation violation - Completeness: parent global_var '{gv.variable}' "
                    f"(op: {gv.op}) is not assigned to any child"
                )
                continue

            child_ops = {c["op"] for c in child_gvs_by_variable[gv.variable]}
            if gv.op == "read_write":
                has_read = "read" in child_ops or "read_write" in child_ops
                has_write = "write" in child_ops or "read_write" in child_ops
                if not (has_read and has_write):
                    errors.append(
                        f"Conservation violation - Completeness: parent requires read+write on "
                        f"'{gv.variable}', but children only provide: {child_ops}"
                    )

        parent_var_names = {gv.variable for gv in parent_gvs}
        for child in node.children:
            for gv in child.global_vars:
                if gv.variable not in parent_var_names:
                    errors.append(
                        f"Conservation violation - Correctness: child '{child.name}' uses "
                        f"undeclared variable '{gv.variable}'"
                    )

        for child in node.children:
            if not child.stop_decompose and child.subprd and child.subprd.global_state_operations:
                errors.append(
                    f"Non-leaf child '{child.name}' has global_state_operations "
                    f"(only leaf nodes should have them)"
                )

        return errors

    def _classify_error(self, error_msg: str) -> ValidationError:
        if error_msg.startswith("Syntax error"):
            return ValidationError("SYNTAX_ERROR", error_msg)
        if "Child functions not used" in error_msg:
            unused_match = re.search(r"\{([^}]+)\}", error_msg)
            unused = [n.strip() for n in unused_match.group(1).split(",")] if unused_match else []
            return ValidationError("UNUSED_CHILD", error_msg, {"unused_children": unused})
        if "Undeclared global variable" in error_msg:
            var_match = re.search(r"Undeclared global variable: (\S+)", error_msg)
            var_name = var_match.group(1) if var_match else ""
            return ValidationError("GLOBAL_VAR_UNDECLARED", error_msg, {"variable": var_name})
        if "Conservation violation" in error_msg:
            return ValidationError("CONSERVATION_VIOLATION", error_msg)
        if error_msg.startswith("DIRECT_RESOURCE_ACCESS_PARENT"):
            return ValidationError("DIRECT_RESOURCE_ACCESS_PARENT", error_msg)
        if error_msg.startswith("CHILD_INPUT_SOURCE_MISSING"):
            child_match = re.search(r"child=([^\s]+)", error_msg)
            arg_match = re.search(r"arg=([^\s]+)", error_msg)
            return ValidationError(
                "CHILD_INPUT_SOURCE_MISSING",
                error_msg,
                {
                    "child": child_match.group(1) if child_match else "",
                    "arg": arg_match.group(1) if arg_match else "",
                }
            )
        if error_msg.startswith("UNGRANTED_INTERFACE_CALL"):
            return ValidationError("UNGRANTED_INTERFACE_CALL", error_msg)
        if error_msg.startswith("INTERFACE_USAGE_VIOLATION"):
            return ValidationError("INTERFACE_USAGE_VIOLATION", error_msg)
        if "Missing parameters" in error_msg or "Extra parameters" in error_msg or "parameter type mismatch" in error_msg:
            return ValidationError("SIGNATURE_MISMATCH", error_msg)
        if "Function name mismatch" in error_msg or "Missing return type" in error_msg or "Return type mismatch" in error_msg:
            return ValidationError("SIGNATURE_MISMATCH", error_msg)
        if "Code is empty" in error_msg or "No function definition" in error_msg:
            return ValidationError("SYNTAX_ERROR", error_msg)
        return ValidationError("UNKNOWN", error_msg)

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

            resource_ok, resource_errors = self.validate_no_direct_resource_access(node, code)
            all_errors.extend(resource_errors)

            iface_ok, iface_errors = self.validate_leaf_interface_usage(node, code)
            all_errors.extend(iface_errors)

            flow_ok, flow_errors = self.validate_child_input_provenance(node, code)
            all_errors.extend(flow_errors)
        
        conservation_errors = self.check_conservation(node)
        all_errors.extend(conservation_errors)

        structured_errors = [self._classify_error(e) for e in all_errors]
        repair_action = self._decide_repair_action(structured_errors, node)
        fix_summary = self._build_fix_summary(structured_errors)

        return ValidationResult(
            passed=len(all_errors) == 0,
            errors=all_errors,
            structured_errors=structured_errors,
            retry_count=node.validation.retry_count,
            repair_action=repair_action,
            fix_summary=fix_summary,
        )
    
    def should_redecompose(self, node: Node, validation: ValidationResult) -> bool:
        if validation.passed:
            return False

        if node.validation.retry_count >= self.config.max_decompose_retries:
            return False

        if validation.repair_action == "redecompose":
            return True

        structural = {
            "UNUSED_CHILD",
            "CANNOT_COMPOSE",
            "CHILD_INPUT_SOURCE_MISSING",
            "DIRECT_RESOURCE_ACCESS_PARENT",
            "CONSERVATION_VIOLATION",
        }
        return any(e.error_type in structural for e in validation.structured_errors)
