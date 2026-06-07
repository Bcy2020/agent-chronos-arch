"""
InterfaceVerifier: Deterministic AST-based verification of generated interface code.
Runs after code generation to enforce contract compliance.
"""
import ast
import re
from typing import Dict, List, Optional, Set

from models import InterfacePlan, InterfaceSpec

PASCAL_CASE_RE = re.compile(r"^[A-Z][a-zA-Z0-9]+$")
BUSINESS_FUNC_NAMES: Set[str] = {
    "pay_order", "ship_order", "cancel_order", "complete_order",
    "deduct_balance", "refund_balance", "approve_order", "reject_order",
}
DISALLOWED_PREFIXES: Set[str] = {"op_root_", "source_id", "global_state"}


class InterfaceVerifier:
    """Deterministic AST verifier for generated interface code.

    Each verify_* method returns a list of error strings.
    Empty list means the check passed.
    """

    def __init__(self, plan: InterfacePlan):
        self._plan = plan
        # Build function_name -> InterfaceSpec mapping
        self._fn_map: Dict[str, InterfaceSpec] = {
            i.function_name: i for i in plan.interfaces
        }
        # Build function_name -> resource_id mapping
        self._fn_resource: Dict[str, str] = {
            i.function_name: i.resource_id for i in plan.interfaces
        }
        # Build resource_id -> set of function_names
        self._resource_fns: Dict[str, Set[str]] = {}
        for i in plan.interfaces:
            self._resource_fns.setdefault(i.resource_id, set()).add(i.function_name)

    def verify(self, code: str) -> List[str]:
        """Run all verification checks. Returns accumulated errors."""
        errors: List[str] = []

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return [f"SYNTAX_ERROR: {e.msg} at line {e.lineno}"]

        errors.extend(self.verify_signatures(code, tree=tree))
        errors.extend(self.verify_no_undeclared_globals(code, tree=tree))
        errors.extend(self.verify_no_business_workflows(code, tree=tree))
        errors.extend(self.verify_list_filters(code, tree=tree))
        errors.extend(self.verify_return_annotations(code, tree=tree))

        return errors

    def verify_signatures(
        self,
        code: str,
        tree: Optional[ast.AST] = None,
    ) -> List[str]:
        """Check all generated function signatures match InterfaceSpec exactly.

        Checks: function name, parameter names (incl. position),
        default-value existence, return annotation.
        """
        if tree is None:
            try:
                tree = ast.parse(code)
            except SyntaxError as e:
                return [f"SYNTAX_ERROR: {e.msg}"]

        errors: List[str] = []
        generated_fns: Dict[str, ast.FunctionDef] = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                generated_fns[node.name] = node

        for fn_name, spec in self._fn_map.items():
            fn_node = generated_fns.get(fn_name)
            if fn_node is None:
                errors.append(
                    f"SIGNATURE_MISMATCH: Interface '{spec.interface_id}': "
                    f"function '{fn_name}' not found in generated code"
                )
                continue

            # Verify param names match
            spec_params = self._extract_param_names(spec.signature)
            gen_params = [arg.arg for arg in fn_node.args.args]

            if spec_params != gen_params:
                errors.append(
                    f"SIGNATURE_MISMATCH: Interface '{spec.interface_id}': "
                    f"function '{fn_name}' params {gen_params} "
                    f"don't match spec {spec_params}"
                )
                continue

            # Verify defaults existence
            spec_defaults = self._extract_defaults_count(spec.signature)
            gen_defaults = len(fn_node.args.defaults)
            if spec_defaults != gen_defaults:
                errors.append(
                    f"SIGNATURE_MISMATCH: Interface '{spec.interface_id}': "
                    f"function '{fn_name}' has {gen_defaults} defaults, "
                    f"spec has {spec_defaults}"
                )
                continue

            # Verify return annotation
            spec_ret = self._extract_return_annotation(spec.signature)
            gen_ret = self._format_annotation(fn_node.returns)
            if spec_ret and gen_ret and spec_ret != gen_ret:
                errors.append(
                    f"SIGNATURE_MISMATCH: Interface '{spec.interface_id}': "
                    f"function '{fn_name}' return '{gen_ret}' "
                    f"doesn't match spec '{spec_ret}'"
                )

        return errors

    def verify_no_undeclared_globals(
        self,
        code: str,
        tree: Optional[ast.AST] = None,
    ) -> List[str]:
        """Check each function only accesses its own resource global variable.

        Checks for:
        - Cross-resource access (e.g., orders function accessing 'users')
        - Disallowed prefixes (op_root_, source_id, global_state)
        """
        if tree is None:
            try:
                tree = ast.parse(code)
            except SyntaxError as e:
                return [f"SYNTAX_ERROR: {e.msg}"]

        errors: List[str] = []

        # Build set of all resource global variable names
        all_resource_globals: Set[str] = {r.resource_id for r in self._plan.resources}

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue

            fn_name = node.name
            resource_id = self._fn_resource.get(fn_name)
            if resource_id is None:
                continue

            declared_global = resource_id

            for child in ast.walk(node):
                if not isinstance(child, ast.Name) or not isinstance(child.ctx, ast.Load):
                    continue
                name = child.id
                # Skip: builtins, context keywords, params
                if self._is_ignored_name(name, node):
                    continue
                if name in {a.arg for a in node.args.args}:
                    continue
                if name in {a.arg for a in node.args.kwonlyargs}:
                    continue
                if name in BUILTIN_NAMES:
                    continue

                # Check disallowed prefixes
                if any(name.startswith(d) for d in DISALLOWED_PREFIXES):
                    errors.append(
                        f"UNDECLARED_GLOBAL: Function '{fn_name}' "
                        f"accesses disallowed global '{name}'"
                    )
                    continue

                # Check cross-resource access only — flag if name matches
                # a DIFFERENT resource's global variable
                if name in all_resource_globals and name != declared_global:
                    errors.append(
                        f"CROSS_RESOURCE_ACCESS: Function '{fn_name}' "
                        f"(resource '{declared_global}') accesses "
                        f"global '{name}' of another resource"
                    )
                    continue

        return errors

    def verify_no_business_workflows(
        self,
        code: str,
        tree: Optional[ast.AST] = None,
    ) -> List[str]:
        """Check no business workflow functions defined or called."""
        if tree is None:
            try:
                tree = ast.parse(code)
            except SyntaxError as e:
                return [f"SYNTAX_ERROR: {e.msg}"]

        errors: List[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for bf in BUSINESS_FUNC_NAMES:
                    if bf in node.name:
                        errors.append(
                            f"BUSINESS_WORKFLOW: Function '{node.name}' "
                            f"declared, matches business name '{bf}'"
                        )

            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in BUSINESS_FUNC_NAMES:
                    errors.append(
                        f"BUSINESS_WORKFLOW: Function calls "
                        f"'{node.func.id}' (business name)"
                    )
                if PASCAL_CASE_RE.match(node.func.id) and node.func.id not in self._fn_map:
                    errors.append(
                        f"BUSINESS_WORKFLOW: Function calls "
                        f"'{node.func.id}' (PascalCase, likely decomposition node)"
                    )

        return errors

    def verify_list_filters(
        self,
        code: str,
        tree: Optional[ast.AST] = None,
    ) -> List[str]:
        """Check that list functions with filter params actually use them in body."""
        if tree is None:
            try:
                tree = ast.parse(code)
            except SyntaxError as e:
                return [f"SYNTAX_ERROR: {e.msg}"]

        errors: List[str] = []

        for fn_name, spec in self._fn_map.items():
            if spec.operation != "list":
                continue

            fn_node = self._find_function(tree, fn_name)
            if fn_node is None:
                continue

            # Params with defaults (after positional params) are "filter" params
            if not fn_node.args.defaults:
                continue  # no filter params

            fn_body_names = {
                n.id for n in ast.walk(fn_node)
                if isinstance(n, ast.Name)
            }

            param_start = len(fn_node.args.args) - len(fn_node.args.defaults)
            for i in range(param_start, len(fn_node.args.args)):
                param_name = fn_node.args.args[i].arg
                if param_name not in fn_body_names:
                    errors.append(
                        f"LIST_FILTER_UNUSED: Interface '{spec.interface_id}': "
                        f"filter parameter '{param_name}' is never used in function body"
                    )

        return errors

    def verify_return_annotations(
        self,
        code: str,
        tree: Optional[ast.AST] = None,
    ) -> List[str]:
        """Heuristic check that return type matches function body behavior."""
        if tree is None:
            try:
                tree = ast.parse(code)
            except SyntaxError as e:
                return [f"SYNTAX_ERROR: {e.msg}"]

        errors: List[str] = []

        for fn_name, spec in self._fn_map.items():
            fn_node = self._find_function(tree, fn_name)
            if fn_node is None:
                continue

            ret_ann = self._format_annotation(fn_node.returns)
            returns = self._collect_returns(fn_node)

            # -> int functions: create should return a key, not a dict
            if spec.operation == "create" and ret_ann in ("int", "str"):
                for ret_stmt in returns:
                    if isinstance(ret_stmt, ast.Dict):
                        errors.append(
                            f"RETURN_TYPE: Interface '{spec.interface_id}': "
                            f"create returns dict but signature says '{ret_ann}'"
                        )

            # -> None functions: update/delete should not return value
            if spec.operation in ("update", "delete") and ret_ann == "None":
                for ret_stmt in returns:
                    if not isinstance(ret_stmt, ast.Constant) or ret_stmt.value is not None:
                        errors.append(
                            f"RETURN_TYPE: Interface '{spec.interface_id}': "
                            f"returns value but signature says '-> None'"
                        )

            # -> bool functions: exists should return bool expression
            if spec.operation == "exists" and ret_ann == "bool":
                for ret_stmt in returns:
                    if self._is_literal_return(ret_stmt):
                        if not isinstance(ret_stmt, (ast.Constant, ast.Name)):
                            pass  # expression-based, likely fine
                        elif isinstance(ret_stmt, ast.Constant) and ret_stmt.value not in (True, False):
                            errors.append(
                                f"RETURN_TYPE: Interface '{spec.interface_id}': "
                                f"exists returns literal, should return bool expression"
                            )

            # -> list[...] functions: list should return something list-like
            if spec.operation == "list" and ret_ann and "list" in ret_ann:
                for ret_stmt in returns:
                    if isinstance(ret_stmt, ast.Constant):
                        errors.append(
                            f"RETURN_TYPE: Interface '{spec.interface_id}': "
                            f"list function returns constant, should return list"
                        )

        return errors

    # === Internal helpers ===

    @staticmethod
    def _extract_param_names(signature: str) -> List[str]:
        """Extract parameter names from signature string."""
        match = re.search(r"def\s+\w+\((.*?)\)", signature)
        if not match:
            return []
        params_str = match.group(1).strip()
        if not params_str:
            return []
        names = []
        for p in params_str.split(","):
            p = p.strip()
            name = p.split(":")[0].strip().split("=")[0].strip()
            if name:
                names.append(name)
        return names

    @staticmethod
    def _extract_defaults_count(signature: str) -> int:
        """Count parameters with default values from signature string."""
        match = re.search(r"def\s+\w+\((.*?)\)", signature)
        if not match:
            return 0
        params_str = match.group(1).strip()
        if not params_str:
            return 0
        count = 0
        for p in params_str.split(","):
            if "=" in p.split(":")[-1] if ":" in p else "=" in p:
                count += 1
        return count

    @staticmethod
    def _extract_return_annotation(signature: str) -> str:
        """Extract return type annotation from signature string."""
        match = re.search(r"->\s*(.*?):?\s*$", signature)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def _format_annotation(ann: Optional[ast.AST]) -> str:
        """Format a type annotation AST node to string."""
        if ann is None:
            return ""
        if isinstance(ann, ast.Name):
            return ann.id
        if isinstance(ann, ast.Constant):
            return str(ann.value)
        if isinstance(ann, ast.Attribute):
            return f"{InterfaceVerifier._format_annotation(ann.value)}.{ann.attr}"
        if isinstance(ann, ast.BinOp):
            left = InterfaceVerifier._format_annotation(ann.left)
            right = InterfaceVerifier._format_annotation(ann.right)
            return f"{left} | {right}"
        if isinstance(ann, ast.Subscript):
            value = InterfaceVerifier._format_annotation(ann.value)
            if value == "?":
                return "?"
            if isinstance(ann.slice, ast.Name):
                return f"{value}[{ann.slice.id}]"
            if isinstance(ann.slice, ast.Tuple):
                elts = ", ".join(
                    InterfaceVerifier._format_annotation(e)
                    for e in ann.slice.elts
                )
                return f"{value}[{elts}]"
            if hasattr(ann.slice, "id"):
                return f"{value}[{ann.slice.id}]"
            if isinstance(ann.slice, ast.Constant):
                return f"{value}[{ann.slice.value}]"
            if isinstance(ann.slice, ast.Subscript):
                return f"{value}[{InterfaceVerifier._format_annotation(ann.slice)}]"
            return "?"
        return "?"

    @staticmethod
    def _find_function(tree: ast.AST, name: str) -> Optional[ast.FunctionDef]:
        """Find a function definition by name in AST."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        return None

    @staticmethod
    def _collect_returns(fn_node: ast.FunctionDef) -> List[ast.AST]:
        """Collect all return statements (values, not None-returns) from a function."""
        returns: List[ast.AST] = []
        for node in ast.walk(fn_node):
            if isinstance(node, ast.Return) and node.value is not None:
                returns.append(node.value)
        return returns

    @staticmethod
    def _is_literal_return(value: ast.AST) -> bool:
        """Check if a return value is a literal (not a complex expression)."""
        return isinstance(value, (ast.Constant, ast.List, ast.Dict, ast.Set, ast.Tuple))

    @staticmethod
    def _is_ignored_name(name: str, fn_node: ast.FunctionDef) -> bool:
        """Check if a name reference should be ignored in global-access checks."""
        # Skip: True/False/None
        if name in {"True", "False", "None"}:
            return True
        # Skip: self (for methods, though we generate functions)
        if name == "self":
            return True
        # Skip: underscore-prefixed Python internals
        if name.startswith("_"):
            return True
        return False


BUILTIN_NAMES: Set[str] = {
    "abs", "all", "any", "bin", "bool", "bytearray", "bytes", "callable",
    "chr", "classmethod", "compile", "complex", "delattr", "dict", "dir",
    "divmod", "enumerate", "eval", "exec", "filter", "float", "format",
    "frozenset", "getattr", "globals", "hasattr", "hash", "hex", "id",
    "input", "int", "isinstance", "issubclass", "iter", "len", "list",
    "locals", "map", "max", "memoryview", "min", "next", "object", "oct",
    "open", "ord", "pow", "print", "property", "range", "repr", "reversed",
    "round", "set", "setattr", "slice", "sorted", "staticmethod", "str",
    "sum", "super", "tuple", "type", "vars", "zip", "__import__",
    "isinstance", "issubclass", "hasattr", "getattr", "setattr", "delattr",
    "Exception", "KeyError", "ValueError", "TypeError", "RuntimeError",
    "IOError", "OSError",
}
