import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capability_allocator import CapabilityAllocator
from models import CapabilityGrant, InterfacePlan, InterfaceSpec, Node


def make_plan(interfaces):
    return InterfacePlan(resources=[], interfaces=interfaces)


def iface(interface_id, resource_id, operation):
    return InterfaceSpec(
        interface_id=interface_id,
        resource_id=resource_id,
        operation=operation,
        function_name=interface_id.replace(".", "_"),
        signature=f"def {interface_id.replace('.', '_')}():",
        description=f"{operation} {resource_id}",
    )


def allocate(requested, interfaces):
    node = Node(node_id="n1", name="Leaf", depth=1, requested_capabilities=requested)
    grant, errors = CapabilityAllocator(make_plan(interfaces)).allocate(node)
    return grant, errors


def test_read_budget_maps_to_read_interfaces():
    grant, errors = allocate(
        ["products.read"],
        [
            iface("products.get", "products", "get"),
            iface("products.list", "products", "list"),
            iface("products.exists", "products", "exists"),
            iface("products.update", "products", "update"),
        ],
    )

    assert errors == []
    assert grant.granted_interfaces == []
    assert grant.candidate_interfaces == [
        "products.get",
        "products.list",
        "products.exists",
    ]


def test_write_budget_maps_to_write_interfaces_only():
    grant, errors = allocate(
        ["products.write"],
        [
            iface("products.get", "products", "get"),
            iface("products.create", "products", "create"),
            iface("products.update", "products", "update"),
            iface("products.delete", "products", "delete"),
        ],
    )

    assert errors == []
    assert grant.candidate_interfaces == [
        "products.create",
        "products.update",
        "products.delete",
    ]


def test_read_write_budget_maps_to_all_compatible_interfaces():
    grant, errors = allocate(
        ["products.read_write"],
        [
            iface("products.get", "products", "get"),
            iface("products.list", "products", "list"),
            iface("products.create", "products", "create"),
            iface("products.update", "products", "update"),
        ],
    )

    assert errors == []
    assert grant.candidate_interfaces == [
        "products.get",
        "products.list",
        "products.create",
        "products.update",
    ]


def test_crud_capability_is_backward_compatible():
    grant, errors = allocate(
        ["products.get"],
        [
            iface("products.get", "products", "get"),
            iface("products.list", "products", "list"),
        ],
    )

    assert errors == []
    assert grant.candidate_interfaces == ["products.get"]


def test_exact_non_resource_interface_id_is_backward_compatible():
    grant, errors = allocate(
        ["lookupProducts"],
        [iface("lookupProducts", "products", "list")],
    )

    assert errors == []
    assert grant.candidate_interfaces == ["lookupProducts"]


def test_unknown_resource_returns_interface_selection_gap():
    grant, errors = allocate(
        ["inventory.read"],
        [iface("products.get", "products", "get")],
    )

    assert grant == CapabilityGrant(node_id="n1", granted_interfaces=[], candidate_interfaces=[])
    assert len(errors) == 1
    assert errors[0].startswith("INTERFACE_SELECTION_GAP")


def test_no_compatible_operation_returns_interface_selection_gap():
    grant, errors = allocate(
        ["products.read"],
        [iface("products.update", "products", "update")],
    )

    assert grant.granted_interfaces == []
    assert grant.candidate_interfaces == []
    assert len(errors) == 1
    assert errors[0].startswith("INTERFACE_SELECTION_GAP")


def test_unknown_operation_returns_interface_selection_gap():
    grant, errors = allocate(
        ["products.archive"],
        [iface("products.get", "products", "get")],
    )

    assert grant.granted_interfaces == []
    assert grant.candidate_interfaces == []
    assert len(errors) == 1
    assert errors[0].startswith("INTERFACE_SELECTION_GAP")
