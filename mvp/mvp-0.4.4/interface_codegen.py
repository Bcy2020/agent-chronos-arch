"""
InterfaceCodeGenerator: Generates interface layer implementation code from InterfacePlan.
This is Phase 3 of the interface layer fix.
The generated code directly accesses global variables (this is the only layer allowed to).
"""
import ast
import re
from typing import Dict, List, Optional

from models import InterfacePlan, ResourceSpec, InterfaceSpec


class InterfaceCodeGenerator:
    def __init__(self):
        pass

    def generate(self, plan: InterfacePlan) -> str:
        lines = []
        lines.append('"""')
        lines.append("Auto-generated interface layer code from InterfacePlan.")
        lines.append("This layer is the ONLY layer allowed to directly access global variables.")
        lines.append('"""')
        lines.append("")
        lines.append("import datetime")
        lines.append("")

        generated_any = False
        for resource in plan.resources:
            resource_interfaces = [
                i for i in plan.interfaces if i.resource_id == resource.resource_id
            ]
            if not resource_interfaces:
                continue
            generated_any = True
            lines.append("")
            lines.append(f"# === Resource: {resource.resource_id} ({resource.storage_model}) ===")
            lines.append(f"# {resource.description}")
            lines.append("")

            if resource.invariants:
                for inv in resource.invariants:
                    lines.append(f"# Invariant: {inv}")
                lines.append("")

            for iface in resource_interfaces:
                func_code = self._generate_interface_function(resource, iface)
                lines.append(func_code)
                lines.append("")

        if not generated_any:
            lines.append("# No resources defined in InterfacePlan")
            lines.append("")

        return "\n".join(lines)

    def _generate_interface_function(self, resource: ResourceSpec, iface: InterfaceSpec) -> str:
        resource_id = resource.resource_id
        params = self._extract_params(iface.signature)
        return_type = self._extract_return_type(iface.signature)

        if resource.storage_model == "dict":
            body = self._generate_dict_body(resource, iface)
        elif resource.storage_model == "list":
            body = self._generate_list_body(resource, iface)
        elif resource.storage_model == "in_memory_table":
            body = self._generate_dict_body(resource, iface)
        else:
            body = f"    # Unsupported storage_model: {resource.storage_model}\n    pass"

        sig = f"def {iface.function_name}{params}"
        if return_type:
            sig += f" -> {return_type}"
        sig += ":"
        lines = [sig]
        if iface.description:
            lines.append(f'    """{iface.description}"""')
        lines.append(body)

        return "\n".join(lines)

    def _extract_params(self, signature: str) -> str:
        match = re.search(r"def\s+\w+(\(.*?\))\s*(->.*?)?:?\s*$", signature)
        if match:
            return match.group(1)
        return "()"

    def _extract_return_type(self, signature: str) -> str:
        match = re.search(r"->\s*(.*?):?\s*$", signature)
        if match:
            return match.group(1).strip()
        return "None"

    def _get_key_field(self, resource: ResourceSpec) -> str:
        if resource.item_schema:
            for field in ["id", "task_id", "order_id", "user_id", "product_id", "key", "code"]:
                if field in resource.item_schema:
                    return field
        return "id"

    def _generate_dict_body(self, resource: ResourceSpec, iface: InterfaceSpec) -> str:
        resource_id = resource.resource_id
        op = iface.operation

        if op == "get":
            return f"    return {resource_id}.get({self._extract_first_arg_name(iface.signature, 'key')})"
        elif op == "list":
            return f"    return list({resource_id}.values())"
        elif op == "create":
            return f"""    new_key = {resource_id}.get('_next_id', 1) if isinstance({resource_id}, dict) and '_next_id' in {resource_id} else len({resource_id}) + 1
    if isinstance(new_key, int) and '_next_id' not in {resource_id}:
        new_key = max({resource_id}.keys()) + 1 if {resource_id} else 1
    {resource_id}[new_key] = {self._extract_first_arg_name(iface.signature, 'item')}
    return {resource_id}[new_key]"""
        elif op == "update":
            key_arg = self._extract_first_arg_name(iface.signature, "key")
            return f"""    if {key_arg} not in {resource_id}:
        return None
    {resource_id}[{key_arg}].update({self._extract_update_arg(iface.signature)})
    return {resource_id}[{key_arg}]"""
        elif op == "delete":
            key_arg = self._extract_first_arg_name(iface.signature, "key")
            return f"""    if {key_arg} not in {resource_id}:
        return False
    del {resource_id}[{key_arg}]
    return True"""
        elif op == "exists":
            return f"    return {self._extract_first_arg_name(iface.signature, 'key')} in {resource_id}"
        else:
            return f"    # Unsupported operation: {op}\n    pass"

    def _generate_list_body(self, resource: ResourceSpec, iface: InterfaceSpec) -> str:
        resource_id = resource.resource_id
        op = iface.operation
        key_field = self._get_key_field(resource)

        if op == "get":
            key_arg = self._extract_first_arg_name(iface.signature, "key")
            return f"""    for item in {resource_id}:
        if isinstance(item, dict) and item.get('{key_field}') == {key_arg}:
            return item
        elif hasattr(item, '{key_field}') and item.{key_field} == {key_arg}:
            return item
    return None"""
        elif op == "list":
            return f"    return list({resource_id})"
        elif op == "create":
            return f"""    {resource_id}.append({self._extract_create_item(iface)})
    return {resource_id}[-1]"""
        elif op == "update":
            key_arg = self._extract_first_arg_name(iface.signature, "key")
            return f"""    for item in {resource_id}:
        if isinstance(item, dict) and item.get('{key_field}') == {key_arg}:
            item.update({self._extract_update_arg(iface.signature)})
            return item
        elif hasattr(item, '{key_field}') and item.{key_field} == {key_arg}:
            for k, v in {self._extract_update_arg(iface.signature)}.items():
                setattr(item, k, v)
            return item
    return None"""
        elif op == "delete":
            key_arg = self._extract_first_arg_name(iface.signature, "key")
            return f"""    for i, item in enumerate({resource_id}):
        if isinstance(item, dict) and item.get('{key_field}') == {key_arg}:
            {resource_id}.pop(i)
            return True
        elif hasattr(item, '{key_field}') and item.{key_field} == {key_arg}:
            {resource_id}.pop(i)
            return True
    return False"""
        elif op == "exists":
            key_arg = self._extract_first_arg_name(iface.signature, "key")
            return f"""    for item in {resource_id}:
        if isinstance(item, dict) and item.get('{key_field}') == {key_arg}:
            return True
        elif hasattr(item, '{key_field}') and item.{key_field} == {key_arg}:
            return True
    return False"""
        else:
            return f"    # Unsupported operation: {op}\n    pass"

    def _extract_first_arg_name(self, signature: str, default: str = "key") -> str:
        params = self._extract_params(signature)
        params = params.strip("()").strip()
        if not params:
            return default
        first_param = params.split(",")[0].strip().split(":")[0].strip()
        return first_param if first_param else default

    def _extract_update_arg(self, signature: str) -> str:
        params = self._extract_params(signature)
        params = params.strip("()").strip()
        if not params:
            return "updates"
        parts = [p.strip().split(":")[0].strip() for p in params.split(",")]
        if len(parts) >= 2:
            return parts[1]
        return "updates"

    def _extract_create_item(self, iface: InterfaceSpec) -> str:
        params = self._extract_params(iface.signature)
        params = params.strip("()").strip()
        if not params:
            return "item"
        parts = [p.strip().split(":")[0].strip() for p in params.split(",")]
        if len(parts) >= 1:
            return parts[0]
        return "item"

    def validate(self, code: str) -> List[str]:
        errors = []
        if not code.strip():
            errors.append("Generated code is empty")
            return errors
        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
        return errors
