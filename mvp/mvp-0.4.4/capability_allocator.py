"""
CapabilityAllocator: Matches leaf node requested_capabilities against InterfacePlan.
This is Phase 4 of the interface layer fix.
Rules:
- Requested interface exists in InterfacePlan → grant it
- Requested interface does not exist → fail
- Do not auto-create new interfaces
"""
from typing import Dict, List, Tuple

from models import InterfacePlan, CapabilityGrant, Node


class CapabilityAllocator:
    def __init__(self, interface_plan: InterfacePlan):
        self._interface_map: Dict[str, bool] = {}
        for iface in interface_plan.interfaces:
            self._interface_map[iface.interface_id] = True

    def allocate(self, node: Node) -> Tuple[CapabilityGrant, List[str]]:
        granted = []
        errors = []
        for req_id in node.requested_capabilities:
            if req_id in self._interface_map:
                granted.append(req_id)
            else:
                errors.append(
                    f"Requested interface '{req_id}' not found in InterfacePlan. "
                    f"Node '{node.name}' requires an interface that was not planned."
                )
        if errors:
            return CapabilityGrant(node_id=node.node_id, granted_interfaces=[]), errors
        return CapabilityGrant(node_id=node.node_id, granted_interfaces=granted), []

    def has_interface(self, interface_id: str) -> bool:
        return interface_id in self._interface_map

    def get_available_interfaces_summary(self) -> str:
        lines = ["Available interfaces:"]
        for iface_id in sorted(self._interface_map.keys()):
            lines.append(f"  - {iface_id}")
        return "\n".join(lines)
