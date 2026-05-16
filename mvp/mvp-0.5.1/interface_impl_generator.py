"""
InterfaceImplementationGenerator: LLM-driven per-resource interface code generation.
Replaces the hardcoded template approach of InterfaceCodeGenerator.
"""
import json
from typing import Any, Dict, List, Tuple

from config import Config
from api_client import APIClient
from models import InterfacePlan, ResourceSpec, InterfaceSpec

SYSTEM_PROMPT = """You are generating the Interface Layer — resource-level access code only.

## Allowed Operations

- **get / exists**: Single-item retrieval and existence check.
- **list**: Return list of items with optional resource-level filtering.
- **create**: Insert item. If return annotation is key type, return the key. If dict/object, return stored item.
- **update**: Patch item by key. Respect return annotation exactly: None → return None, bool → return success, dict → return updated object.
- **delete**: Remove item by key. Respect return annotation: None → return None, bool → return success.

## Operation Semantics (fixed rules)

- `get`: Return None if item is missing (unless spec says otherwise).
- `list`: Filter parameters may only match against fields in item_schema. Do NOT perform workflow or business decisions.
- `create`: Generate a new key only if needed. If return annotation is key type (int, str), return the generated key. If dict/object, return the stored item.
- `update`: Patch fields on the existing item. Respect return annotation.
- `delete`: Remove the item. Respect return annotation.
- `exists`: Return bool.

## Forbidden

- Business workflows (pay_order, ship_order, cancel_order, complete_order, deduct_balance, etc.)
- Cross-resource transactions (accessing multiple global variables)
- Calling decomposition node functions (anything with PascalCase names like CreateOrder, PayOrder)
- Inventing undeclared functions
- Accessing undeclared global variables
- Adapting to downstream leaf code
- Import of external libraries beyond standard library

## Output Format

Return ONLY valid JSON with this structure:
{
  "code": "...full python code for ALL interfaces of this resource (no markdown fence)...",
  "notes": ["...", "..."],
  "assumptions": ["...", "..."]
}

The `code` field must contain ONLY the function definitions. No markdown fences, no module docstrings. Each function must include its full signature and body. Use idiomatic Python dict operations (`.get()`, `in`, `[]`, `.update()`)."""


class InterfaceImplementationGenerator:
    """LLM-driven interface implementation generator.

    Generates code per-resource, then assembles the final interfaces.py.
    """

    def __init__(self, config: Config, api_client: APIClient):
        self.config = config
        self.api_client = api_client

    def generate(self, plan: InterfacePlan) -> str:
        """Generate complete interfaces.py from InterfacePlan.

        Groups interfaces by resource, generates per-resource via LLM,
        then assembles into final output.
        """
        resource_codes: List[Dict] = []

        for resource in plan.resources:
            resource_interfaces = [
                i for i in plan.interfaces
                if i.resource_id == resource.resource_id
            ]
            if not resource_interfaces:
                continue

            result = self._generate_for_resource(resource, resource_interfaces)
            resource_codes.append(result)

            notes = result.get("notes", [])
            if notes:
                print(f"  [{resource.resource_id}] Notes: {'; '.join(notes)}")
            assumptions = result.get("assumptions", [])
            if assumptions:
                print(f"  [{resource.resource_id}] Assumptions: {'; '.join(assumptions)}")

        return self._assemble(plan, resource_codes)

    def _generate_for_resource(
        self,
        resource: ResourceSpec,
        interfaces: List[InterfaceSpec],
    ) -> Dict[str, Any]:
        """Generate interface code for a single resource via LLM.

        Returns dict with 'resource_id', 'code', 'notes', 'assumptions'.
        """
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": self._build_user_prompt(resource, interfaces)},
        ]

        try:
            response = self.api_client.chat(messages, max_tokens=4096)
        except Exception as e:
            print(f"  LLM call failed for '{resource.resource_id}': {e}")
            return {
                "resource_id": resource.resource_id,
                "code": self._fallback_template(resource, interfaces),
                "notes": [f"LLM call failed, fallback template used: {e}"],
                "assumptions": [],
            }

        parsed = self._parse_response(response)
        if "error" in parsed:
            print(f"  Parse failed for '{resource.resource_id}': {parsed['error']}")
            return {
                "resource_id": resource.resource_id,
                "code": self._fallback_template(resource, interfaces),
                "notes": [f"Parse failed, fallback template used: {parsed['error']}"],
                "assumptions": [],
            }

        return {
            "resource_id": resource.resource_id,
            "code": parsed.get("code", ""),
            "notes": parsed.get("notes", []),
            "assumptions": parsed.get("assumptions", []),
        }

    def _build_user_prompt(
        self,
        resource: ResourceSpec,
        interfaces: List[InterfaceSpec],
    ) -> str:
        """Build user prompt for a single resource."""
        resource_json = json.dumps(resource.to_dict(), indent=2)
        interfaces_json = json.dumps(
            [i.to_dict() for i in interfaces],
            indent=2,
        )

        lines = [
            f"Generate interface code for resource: {resource.resource_id}",
            "",
            "=" * 60,
            "RESOURCE SPEC",
            "=" * 60,
            resource_json,
            "",
            "=" * 60,
            f"INTERFACES ({len(interfaces)} functions to generate)",
            "=" * 60,
            interfaces_json,
            "",
            "=" * 60,
            "GLOBAL BINDING",
            "=" * 60,
            f"Allowed global variable: {resource.resource_id}",
            f"Do NOT access any other global variable.",
            "",
            "=" * 60,
            "FUNCTIONS TO GENERATE",
            "=" * 60,
        ]
        for i in interfaces:
            lines.append(f"  {i.signature}")
            lines.append(f"    Description: {i.description}")
            if i.preconditions:
                lines.append(f"    Preconditions: {i.preconditions}")
            if i.postconditions:
                lines.append(f"    Postconditions: {i.postconditions}")
            lines.append("")

        lines.append("Generate ONLY the functions listed above. Do NOT invent extra functions.")
        return "\n".join(lines)

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """Parse LLM JSON response with markdown fence stripping."""
        content = content.strip()
        if content.startswith("```"):
            content = self._strip_markdown_fence(content)
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            return {"error": str(e)}

    @staticmethod
    def _strip_markdown_fence(content: str) -> str:
        """Strip markdown code fences from LLM output."""
        import re
        content = re.sub(r"^```[a-zA-Z0-9]*\n?", "", content)
        content = re.sub(r"\n?```$", "", content)
        return content.strip()

    def _fallback_template(
        self,
        resource: ResourceSpec,
        interfaces: List[InterfaceSpec],
    ) -> str:
        """Fallback: generate simple code when LLM call fails.

        Uses basic template similar to old InterfaceCodeGenerator.
        This ensures the pipeline doesn't break on API failures.
        """
        lines = []
        for iface in interfaces:
            sig = iface.signature
            op = iface.operation
            var = resource.resource_id

            lines.append(f"    # {iface.description}")
            lines.append(f"    {sig}")

            if op == "get":
                arg = self._extract_param_name(sig, 0, "key")
                lines.append(f"        return {var}.get({arg})")
            elif op == "exists":
                arg = self._extract_param_name(sig, 0, "key")
                lines.append(f"        return {arg} in {var}")
            elif op == "list":
                lines.append(f"        return list({var}.values())")
            elif op == "create":
                item_arg = self._extract_param_name(sig, 0, "item")
                lines.append(f"        new_key = 1")
                lines.append(f"        if {var}:")
                lines.append(f"            new_key = max({var}.keys()) + 1")
                lines.append(f"        {var}[new_key] = {item_arg}")
                lines.append(f"        return new_key")
            elif op == "update":
                key_arg = self._extract_param_name(sig, 0, "key")
                update_arg = self._extract_param_name(sig, 1, "updates")
                lines.append(f"        if {key_arg} not in {var}:")
                lines.append(f"            return None")
                lines.append(f"        {var}[{key_arg}].update({update_arg})")
                ret_type = self._extract_return_annotation(sig)
                if ret_type == "None":
                    lines.append(f"        return None")
                else:
                    lines.append(f"        return {var}[{key_arg}]")
            elif op == "delete":
                key_arg = self._extract_param_name(sig, 0, "key")
                lines.append(f"        if {key_arg} not in {var}:")
                lines.append(f"            return False")
                lines.append(f"        del {var}[{key_arg}]")
                lines.append(f"        return True")
            else:
                lines.append(f"        pass")

            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _extract_param_name(signature: str, index: int, default: str) -> str:
        """Extract parameter name from signature by position."""
        import re
        match = re.search(r"def\s+\w+\((.*?)\)", signature)
        if not match:
            return default
        params_str = match.group(1).strip()
        if not params_str:
            return default
        parts = [p.strip().split(":")[0].strip().split("=")[0].strip()
                 for p in params_str.split(",")]
        if index < len(parts) and parts[index]:
            return parts[index]
        return default

    @staticmethod
    def _extract_return_annotation(signature: str) -> str:
        """Extract return type annotation from signature."""
        import re
        match = re.search(r"->\s*(.*?):?\s*$", signature)
        if match:
            return match.group(1).strip()
        return "None"

    def _assemble(
        self,
        plan: InterfacePlan,
        resource_codes: List[Dict],
    ) -> str:
        """Assemble per-resource code blocks into final interfaces.py."""
        lines = []
        lines.append('"""')
        lines.append("Auto-generated interface layer code from InterfacePlan.")
        lines.append("This layer is the ONLY layer allowed to directly access global variables.")
        lines.append('"""')
        lines.append("")
        lines.append("import datetime")
        lines.append("")

        seen_functions: set = set()
        for rc in resource_codes:
            resource_id = rc["resource_id"]
            code = rc.get("code", "").strip()

            lines.append("")
            lines.append(f"# === Resource: {resource_id} ===")
            lines.append("")

            if not code:
                lines.append(f"# No code generated for {resource_id}")
                continue

            # Check for duplicate function names
            for line in code.split("\n"):
                func_match = __import__("re").match(
                    r"^\s*def\s+(\w+)\s*\(", line
                )
                if func_match:
                    fname = func_match.group(1)
                    if fname in seen_functions:
                        print(
                            f"  WARNING: Duplicate function '{fname}' "
                            f"in resource '{resource_id}', skipping"
                        )
                        continue
                    seen_functions.add(fname)

            lines.append(code)

        if not resource_codes:
            lines.append("# No resources defined in InterfacePlan")
            lines.append("")

        return "\n".join(lines)
