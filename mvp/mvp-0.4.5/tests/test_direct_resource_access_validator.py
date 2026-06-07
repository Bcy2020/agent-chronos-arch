"""
Tests for validate_no_direct_resource_access scope-aware local binding handling.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from models import DataSource, GlobalVar, Node
from validator import Validator


def check_resource_access(code, resource_names, expect_pass, node_children=1):
    val = Validator(Config(api_key="test"))
    val._resource_names = set(resource_names)

    node = Node("", "TestNode", 0, children=[Node("", "Child", 1)] if node_children else [])
    node.data_sources = [DataSource(name, "memory", "read_write") for name in resource_names]
    node.global_vars = [GlobalVar(name, "read_write") for name in resource_names]

    ok, errs = val.validate_no_direct_resource_access(node, code)
    assert ok == expect_pass, errs
    return errs


def test_pass_local_child_return_shadow():
    check_resource_access(
        """
def TestNode(input):
    orders = ListOrders(user_filter, status_filter)
    return {"orders": orders}
""",
        {"orders"},
        True,
    )


def test_pass_tuple_child_return_shadow():
    check_resource_access(
        """
def TestNode(input):
    orders, total_spent, status_counts = GetUserOrders(user_id)
    return {"orders": orders, "total_spent": total_spent}
""",
        {"orders"},
        True,
    )


def test_pass_products_child_return_shadow():
    check_resource_access(
        """
def TestNode(input):
    products = ListProducts(low_stock)
    return {"products": products}
""",
        {"products"},
        True,
    )


def test_pass_for_loop_target_shadow():
    check_resource_access(
        """
def TestNode(input):
    for orders in fetch_all():
        process(orders)
""",
        {"orders"},
        True,
    )


def test_pass_with_stmt_var_shadow():
    check_resource_access(
        """
def TestNode(input):
    with open_orders() as orders:
        return orders
""",
        {"orders"},
        True,
    )


def test_pass_except_handler_shadow():
    check_resource_access(
        """
def TestNode(input):
    try:
        result = ChildA()
    except Exception as orders:
        return None
""",
        {"orders"},
        True,
    )


def test_pass_import_shadows_resource():
    check_resource_access(
        """
def TestNode(input):
    import json as orders
    return orders.dumps(data)
""",
        {"orders"},
        True,
    )


def test_pass_param_name_shadows_resource():
    check_resource_access(
        """
def TestNode(orders):
    return orders
""",
        {"orders"},
        True,
    )


def test_pass_annassign_target_shadow():
    check_resource_access(
        """
def TestNode(input):
    orders: List[dict] = ListOrders(user_filter, status_filter)
    return {"orders": orders}
""",
        {"orders"},
        True,
    )


def test_pass_augassign_after_local_init():
    check_resource_access(
        """
def TestNode(input):
    orders = []
    orders += ChildFetch()
    return {"orders": orders}
""",
        {"orders"},
        True,
    )


def test_pass_dataflow_conformance_style():
    check_resource_access(
        """
def TestNode(input):
    orders = ListOrders(user_filter, status_filter)
    products = ListProducts(low_stock)
    return {"success": True, "orders": orders, "products": products}
""",
        {"orders", "products"},
        True,
    )


def test_pass_nested_local_binding_does_not_pollute_outer_when_outer_has_own_binding():
    check_resource_access(
        """
def TestNode(input):
    def inner():
        orders = ChildFetch()
        return orders
    orders = ListOrders()
    return orders
""",
        {"orders"},
        True,
    )


def test_fail_unbound_bare_resource_read():
    check_resource_access(
        """
def TestNode(input):
    return {"orders": orders}
""",
        {"orders"},
        False,
    )


def test_fail_unbound_resource_subscript():
    errs = check_resource_access(
        """
def TestNode(input):
    order = orders[order_id]
    return order
""",
        {"orders"},
        False,
    )
    assert errs == ["DIRECT_RESOURCE_ACCESS_PARENT: resource=orders subscript"]


def test_fail_unbound_resource_attribute():
    errs = check_resource_access(
        """
def TestNode(input):
    return orders.get(order_id)
""",
        {"orders"},
        False,
    )
    assert errs == ["DIRECT_RESOURCE_ACCESS_PARENT: resource=orders attr=get"]


def test_fail_unbound_resource_passed_to_child():
    check_resource_access(
        """
def TestNode(input):
    return SomeChild(orders)
""",
        {"orders"},
        False,
    )


def test_fail_global_declared_resource():
    check_resource_access(
        """
def TestNode(input):
    global orders
    return orders
""",
        {"orders"},
        False,
    )


def test_fail_resource_in_if_condition():
    check_resource_access(
        """
def TestNode(input):
    if orders:
        return ChildA()
""",
        {"orders"},
        False,
    )


def test_fail_resource_in_comprehension():
    check_resource_access(
        """
def TestNode(input):
    results = [x for x in orders]
    return results
""",
        {"orders"},
        False,
    )


def test_fail_unbound_resource_augassign():
    check_resource_access(
        """
def TestNode(input):
    orders += ChildFetch()
    return orders
""",
        {"orders"},
        False,
    )


def test_fail_read_before_local_assignment():
    check_resource_access(
        """
def TestNode(input):
    result = orders
    orders = ChildFetch()
    return result
""",
        {"orders"},
        False,
    )


def test_fail_nested_binding_does_not_shadow_outer_resource_read():
    check_resource_access(
        """
def TestNode(input):
    def inner():
        orders = ChildFetch()
        return orders
    return orders
""",
        {"orders"},
        False,
    )


def test_pass_nested_global_decl_does_not_affect_outer_local_binding():
    check_resource_access(
        """
def TestNode(input):
    def inner():
        global orders
        return None
    orders = ChildFetch()
    return orders
""",
        {"orders"},
        True,
    )
