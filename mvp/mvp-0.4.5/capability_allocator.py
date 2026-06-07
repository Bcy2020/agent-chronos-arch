"""
CapabilityAllocator: Resolves leaf requested_capabilities to interface candidates.

requested_capabilities are resource-operation budgets, not concrete interface ids.
The allocator never expands a node's resource boundary; it only finds interfaces
inside the already requested resource/operation budget.
"""
from typing import Dict, List, Set, Tuple

from models import InterfacePlan, CapabilityGrant, InterfaceSpec, Node


READ_INTERFACE_OPS = {"get", "list", "exists"}
WRITE_INTERFACE_OPS = {"create", "update", "delete"}
ACCESS_TO_INTERFACE_OPS = {
    "read": READ_INTERFACE_OPS,
    "write": WRITE_INTERFACE_OPS,
    "read_write": READ_INTERFACE_OPS | WRITE_INTERFACE_OPS,
}
CRUD_INTERFACE_OPS = READ_INTERFACE_OPS | WRITE_INTERFACE_OPS


class CapabilityAllocator:
    def __init__(self, interface_plan: InterfacePlan):
        self._interface_map: Dict[str, InterfaceSpec] = {}
        self._interfaces_by_resource: Dict[str, List[InterfaceSpec]] = {}
        for iface in interface_plan.interfaces:
            self._interface_map[iface.interface_id] = iface
            self._interfaces_by_resource.setdefault(iface.resource_id, []).append(iface)

    def allocate(self, node: Node) -> Tuple[CapabilityGrant, List[str]]:
        candidates: List[str] = []
        errors = []
        for req_id in node.requested_capabilities:
            matched, req_errors = self._candidate_interfaces_for_request(req_id, node.name)
            if req_errors:
                errors.extend(req_errors)
                continue
            candidates.extend(matched)

        if errors:
            return CapabilityGrant(
                node_id=node.node_id,
                granted_interfaces=[],
                candidate_interfaces=[],
            ), errors

        return CapabilityGrant(
            node_id=node.node_id,
            granted_interfaces=[],
            candidate_interfaces=self._dedupe(candidates),
        ), []

    def has_interface(self, interface_id: str) -> bool:
        return interface_id in self._interface_map

    def get_available_interfaces_summary(self) -> str:
        lines = ["Available interfaces:"]
        for iface_id in sorted(self._interface_map.keys()):
            iface = self._interface_map[iface_id]
            lines.append(
                f"  - {iface.interface_id}: {iface.signature} "
                f"(resource={iface.resource_id}, operation={iface.operation})"
            )
        return "\n".join(lines)

    def _candidate_interfaces_for_request(self, req_id: str, node_name: str) -> Tuple[List[str], List[str]]:
        exact = self._interface_map.get(req_id)
        if exact and "." not in req_id:
            return [exact.interface_id], []

        if "." not in req_id:
            return [], [
                f"INTERFACE_SELECTION_GAP: capability '{req_id}' for node '{node_name}' "
                f"must be 'resource.operation' or an existing interface_id."
            ]

        resource_id, requested_op = req_id.rsplit(".", 1)
        if not resource_id or not requested_op:
            return [], [
                f"INTERFACE_SELECTION_GAP: malformed capability '{req_id}' for node '{node_name}'."
            ]

        if resource_id not in self._interfaces_by_resource:
            if req_id in self._interface_map:
                return [req_id], []
            return [], [
                f"INTERFACE_SELECTION_GAP: capability '{req_id}' for node '{node_name}' "
                f"references unknown resource '{resource_id}'."
            ]

        compatible_ops = self._compatible_interface_ops(requested_op)
        if not compatible_ops:
            if req_id in self._interface_map:
                return [req_id], []
            return [], [
                f"INTERFACE_SELECTION_GAP: capability '{req_id}' for node '{node_name}' "
                f"uses unsupported operation '{requested_op}'."
            ]

        matches = [
            iface.interface_id
            for iface in self._interfaces_by_resource[resource_id]
            if iface.operation in compatible_ops
        ]
        if not matches:
            return [], [
                f"INTERFACE_SELECTION_GAP: capability '{req_id}' for node '{node_name}' "
                f"has no compatible interface in InterfacePlan."
            ]

        return matches, []

    def _compatible_interface_ops(self, requested_op: str) -> Set[str]:
        if requested_op in ACCESS_TO_INTERFACE_OPS:
            return ACCESS_TO_INTERFACE_OPS[requested_op]
        if requested_op in CRUD_INTERFACE_OPS:
            return {requested_op}
        return set()

    def _dedupe(self, interface_ids: List[str]) -> List[str]:
        seen = set()
        result = []
        for interface_id in interface_ids:
            if interface_id in seen:
                continue
            seen.add(interface_id)
            result.append(interface_id)
        return result
