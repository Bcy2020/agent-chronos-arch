"""
Interface Planner: Generates InterfacePlan from JsonPRD.
Placed between JSON PRD conversion and tree decomposition.
Phase 2 of interface_layer_fix_doc.
"""
import json
from datetime import datetime
from typing import Any, Dict, List

from config import Config
from api_client import APIClient
from models import JsonPRD, ResourceSpec, InterfaceSpec, InterfacePlan

INTERFACE_PLANNER_SYSTEM_PROMPT = """You are a resource interface designer. Your task is to analyze a JSON PRD and design low-level resource access interfaces.

## Core Rules

1. You are NOT implementing business logic. You are ONLY designing low-level resource access interfaces.
2. Do NOT create domain-specific business actions such as `pay_order`, `ship_order`, or `cancel_order`.
3. Prefer generic CRUD-like interfaces (get, list, create, update, delete, exists).

## Storage Model Whitelist (choose only from these)

- `dict`: Key-value storage, fast access by key. Use when entities have unique IDs.
- `list`: Ordered list, suitable for iteration and search. Use when sequential access is needed.
- `in_memory_table`: Table structure with multi-field query support. Use when entities need filtering by multiple fields.

## Operation Whitelist (choose only from these)

- `get`: Retrieve a single entity by ID/key.
- `list`: List/search multiple entities, optionally with filters.
- `create`: Create a new entity.
- `update`: Update an existing entity.
- `delete`: Delete an entity.
- `exists`: Check whether an entity exists.

## Output Requirements

- Analyze each data source in the PRD.
- For each data source, choose ONE storage model.
- For each data source, design the necessary CRUD interfaces.
- Every data source must have at least a `get` interface.
- If a data source needs modification, include `create`, `update`, `delete` as needed.
- Return ONLY valid JSON with the exact structure specified.

## JSON Output Structure
{
  "resources": [
    {
      "resource_id": "name of the data source",
      "description": "what this resource stores",
      "storage_model": "dict or list or in_memory_table",
      "key_type": "type of the key (null if not applicable)",
      "value_type": "type of the value/item",
      "item_schema": {
        "field_name": "field_type"
      },
      "invariants": [
        "data integrity rules"
      ]
    }
  ],
  "interfaces": [
    {
      "interface_id": "resource_name.operation_name",
      "resource_id": "which resource this interface operates on",
      "operation": "get or list or create or update or delete or exists",
      "function_name": "snake_case_function_name",
      "signature": "def function_name(params) -> return_type",
      "description": "what this function does",
      "preconditions": ["conditions that must be true before call"],
      "postconditions": ["conditions that will be true after call"]
    }
  ]
}
"""


class InterfacePlanner:
    def __init__(self, config: Config, api_client: APIClient):
        self.config = config
        self.api_client = api_client

    def _build_user_prompt(self, json_prd: JsonPRD) -> str:
        prd_dict = json_prd.to_dict()
        prd_json = json.dumps(prd_dict, indent=2, ensure_ascii=False)

        prompt = f"""Analyze the following JSON PRD and design resource access interfaces.

JSON PRD:
```json
{prd_json}
```

Remember:
- Choose storage model from: dict, list, in_memory_table
- Choose operations from: get, list, create, update, delete, exists
- Do NOT create business action interfaces like pay_order or ship_order
- Create only low-level CRUD interfaces
- Every resource needs at least a get interface
"""
        return prompt

    def plan(self, json_prd: JsonPRD) -> InterfacePlan:
        messages = [
            {"role": "system", "content": INTERFACE_PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": self._build_user_prompt(json_prd)}
        ]

        response = self.api_client.chat(messages, max_tokens=8192)

        parsed = self._parse_response(response)
        plan = self._response_to_plan(parsed)
        errors = self.validate_plan(plan)

        if errors:
            print(f"InterfacePlan validation warnings ({len(errors)}):")
            for e in errors:
                print(f"  - {e}")

        return plan

    def _parse_response(self, response: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(response)
            return parsed
        except json.JSONDecodeError as e:
            print(f"Failed to parse LLM response as JSON: {e}")
            return {"resources": [], "interfaces": []}

    def _response_to_plan(self, data: Dict[str, Any]) -> InterfacePlan:
        resources = []
        for r in data.get("resources", []):
            resources.append(ResourceSpec(
                resource_id=r.get("resource_id", ""),
                description=r.get("description", ""),
                storage_model=r.get("storage_model", "dict"),
                key_type=r.get("key_type"),
                value_type=r.get("value_type"),
                item_schema=r.get("item_schema", {}),
                invariants=r.get("invariants", [])
            ))

        interfaces = []
        for i in data.get("interfaces", []):
            interfaces.append(InterfaceSpec(
                interface_id=i.get("interface_id", ""),
                resource_id=i.get("resource_id", ""),
                operation=i.get("operation", "read"),
                function_name=i.get("function_name", ""),
                signature=i.get("signature", ""),
                description=i.get("description", ""),
                preconditions=i.get("preconditions", []),
                postconditions=i.get("postconditions", [])
            ))

        return InterfacePlan(
            resources=resources,
            interfaces=interfaces,
            created_at=datetime.now().isoformat()
        )

    def validate_plan(self, plan: InterfacePlan) -> List[str]:
        errors = []

        valid_storage_models = {"dict", "list", "in_memory_table"}
        valid_operations = {"get", "list", "create", "update", "delete", "exists"}

        for resource in plan.resources:
            if resource.storage_model not in valid_storage_models:
                errors.append(f"Resource '{resource.resource_id}': invalid storage_model '{resource.storage_model}'")

        resource_ids = {r.resource_id for r in plan.resources}

        for interface in plan.interfaces:
            if interface.operation not in valid_operations:
                errors.append(f"Interface '{interface.interface_id}': invalid operation '{interface.operation}'")
            if interface.resource_id not in resource_ids:
                errors.append(f"Interface '{interface.interface_id}': references unknown resource '{interface.resource_id}'")

        for resource_id in resource_ids:
            has_get = any(
                i.resource_id == resource_id and i.operation == "get"
                for i in plan.interfaces
            )
            if not has_get:
                errors.append(f"Resource '{resource_id}': missing required 'get' interface")

        return errors
