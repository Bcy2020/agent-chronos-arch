"""
InterfaceNormalizer: Deterministic normalization and validation of InterfacePlan.
Runs after InterfacePlanner output, before code generation.
"""
import ast
import re
from typing import List, Set

from models import InterfacePlan, ResourceSpec, InterfaceSpec

BUSINESS_ACTION_PATTERNS: Set[str] = {
    r"pay_", r"ship_", r"cancel_", r"complete_", r"deduct_",
    r"refund_", r"approve_", r"reject_", r"confirm_", r"authorize_",
    r"validate_", r"notify_", r"dispatch_",
}

BUSINESS_PARAM_PATTERNS: Set[str] = {
    r"^payment", r"^shipping", r"^discount", r"^coupon", r"^tax",
    r"^invoice", r"^receipt",
}

VALID_OPERATIONS: Set[str] = {"get", "list", "create", "update", "delete", "exists"}


class InterfaceNormalizer:
    """Deterministic normalizer and validator for InterfacePlan."""

    def normalize_plan(self, plan: InterfacePlan) -> InterfacePlan:
        """Normalize InterfacePlan in-place and return it."""
        for i in plan.interfaces:
            sig = i.signature
            sig = sig.strip()
            if not sig.endswith(":"):
                sig += ":"
            sig = re.sub(r"\s+", " ", sig)
            i.signature = sig
        return plan

    def validate_plan(self, plan: InterfacePlan) -> List[str]:
        """Run all structural validation checks. Returns list of error messages."""
        errors: List[str] = []

        resource_ids = {r.resource_id for r in plan.resources}

        errors.extend(self._validate_resources(plan.resources))
        errors.extend(self._validate_interfaces(plan.interfaces, resource_ids))
        errors.extend(self._validate_signatures_parsable(plan.interfaces))
        errors.extend(self._validate_function_names(plan.interfaces))
        errors.extend(self.check_no_business_actions(plan.interfaces))

        return errors

    def _validate_resources(self, resources: List[ResourceSpec]) -> List[str]:
        errors = []
        valid_storage = {"dict", "list", "in_memory_table"}
        seen_ids: Set[str] = set()
        for r in resources:
            if not r.resource_id:
                errors.append("Resource missing resource_id")
            if r.resource_id in seen_ids:
                errors.append(f"Duplicate resource_id: '{r.resource_id}'")
            seen_ids.add(r.resource_id)
            if r.storage_model not in valid_storage:
                errors.append(
                    f"Resource '{r.resource_id}': invalid storage_model "
                    f"'{r.storage_model}' (must be one of {valid_storage})"
                )
        return errors

    def _validate_interfaces(
        self, interfaces: List[InterfaceSpec], resource_ids: Set[str]
    ) -> List[str]:
        errors = []
        seen_ids: Set[str] = set()
        for i in interfaces:
            if not i.interface_id:
                errors.append("Interface missing interface_id")
            if i.interface_id in seen_ids:
                errors.append(f"Duplicate interface_id: '{i.interface_id}'")
            seen_ids.add(i.interface_id)

            if i.operation not in VALID_OPERATIONS:
                errors.append(
                    f"Interface '{i.interface_id}': invalid operation "
                    f"'{i.operation}' (must be one of {VALID_OPERATIONS})"
                )
            if i.resource_id not in resource_ids:
                errors.append(
                    f"Interface '{i.interface_id}': references unknown "
                    f"resource '{i.resource_id}'"
                )
            if not i.function_name:
                errors.append(f"Interface '{i.interface_id}': missing function_name")

        for resource_id in resource_ids:
            has_get = any(
                i.resource_id == resource_id and i.operation == "get"
                for i in interfaces
            )
            if not has_get:
                errors.append(f"Resource '{resource_id}': missing required 'get' interface")

        return errors

    @staticmethod
    def _parse_signature_safe(sig: str) -> ast.FunctionDef | None:
        """Wrap signature with a dummy body so ast.parse accepts it."""
        try:
            tree = ast.parse(sig.strip() + "\n    pass")
            if tree.body and isinstance(tree.body[0], ast.FunctionDef):
                return tree.body[0]
        except SyntaxError:
            pass
        return None

    def _validate_signatures_parsable(self, interfaces: List[InterfaceSpec]) -> List[str]:
        errors = []
        for i in interfaces:
            sig = i.signature.strip()
            fn = self._parse_signature_safe(sig)
            if fn is None:
                try:
                    ast.parse(sig)
                    errors.append(
                        f"Interface '{i.interface_id}': signature does not "
                        f"parse as a function definition: '{sig}'"
                    )
                except SyntaxError as e:
                    errors.append(
                        f"Interface '{i.interface_id}': signature syntax error: "
                        f"{e.msg} in '{sig}'"
                    )
        return errors

    def _validate_function_names(self, interfaces: List[InterfaceSpec]) -> List[str]:
        errors = []
        for i in interfaces:
            fn = self._parse_signature_safe(i.signature)
            if fn is not None:
                if fn.name != i.function_name:
                    errors.append(
                        f"Interface '{i.interface_id}': function_name "
                        f"'{i.function_name}' does not match signature "
                        f"declared name '{fn.name}'"
                    )
        return errors

    def check_no_business_actions(self, interfaces: List[InterfaceSpec]) -> List[str]:
        errors = []
        for i in interfaces:
            fn_name = i.function_name
            for pattern in BUSINESS_ACTION_PATTERNS:
                if re.search(pattern, fn_name):
                    errors.append(
                        f"Interface '{i.interface_id}': function_name "
                        f"'{fn_name}' matches business action pattern '{pattern}'"
                    )
                    break

            fn = self._parse_signature_safe(i.signature)
            if fn is not None:
                for arg in fn.args.args:
                    arg_name = arg.arg
                    for param_pattern in BUSINESS_PARAM_PATTERNS:
                        if re.search(param_pattern, arg_name):
                            errors.append(
                                f"Interface '{i.interface_id}': parameter "
                                f"'{arg_name}' matches business parameter "
                                f"pattern '{param_pattern}'"
                            )

        return errors

    def plan_summary(self, plan: InterfacePlan) -> str:
        """Return a human-readable summary of the plan."""
        lines = [
            f"InterfacePlan: {len(plan.resources)} resources, "
            f"{len(plan.interfaces)} interfaces",
            f"Created: {plan.created_at}",
        ]
        for r in plan.resources:
            res_ifaces = [i for i in plan.interfaces if i.resource_id == r.resource_id]
            lines.append(
                f"  {r.resource_id} ({r.storage_model}): "
                f"{len(res_ifaces)} interfaces"
            )
            for i in res_ifaces:
                lines.append(f"    {i.operation}: {i.signature}")
        return "\n".join(lines)
