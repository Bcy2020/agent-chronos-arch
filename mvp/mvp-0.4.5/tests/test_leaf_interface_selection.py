import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from code_generator import CodeGenerator
from config import Config
from models import (
    Boundary,
    CapabilityGrant,
    InterfacePlan,
    InterfaceSpec,
    InputParam,
    Node,
    OutputParam,
)


class FakeAPIClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.messages = []

    def chat(self, messages, max_tokens=2048):
        self.messages.append(messages)
        if not self.responses:
            return json.dumps({"code": "", "error": "No more fake responses"})
        return json.dumps(self.responses.pop(0))


def iface(interface_id, operation, function_name, signature, description):
    return InterfaceSpec(
        interface_id=interface_id,
        resource_id="products",
        operation=operation,
        function_name=function_name,
        signature=signature,
        description=description,
    )


def make_generator(responses):
    client = FakeAPIClient(responses)
    generator = CodeGenerator(Config(api_key="test"), client)
    generator.set_interface_plan(InterfacePlan(
        resources=[],
        interfaces=[
            iface(
                "products.get",
                "get",
                "get_product",
                "def get_product(product_id: int) -> dict | None:",
                "Retrieve one product.",
            ),
            iface(
                "products.list",
                "list",
                "list_products",
                "def list_products(low_stock: bool = False) -> list[dict]:",
                "List products.",
            ),
        ],
    ))
    return generator, client


def make_leaf():
    return Node(
        node_id="leaf_1",
        name="QueryProduct",
        depth=2,
        purpose="Return one product by id",
        inputs=[InputParam("product_id", "int", "Product id")],
        outputs=[OutputParam("product", "dict", "Product row")],
        boundary=Boundary(
            in_scope=["read one product"],
            out_of_scope=["list products", "update products"],
        ),
        requested_capabilities=["products.read"],
        granted_capabilities=CapabilityGrant(
            node_id="leaf_1",
            candidate_interfaces=["products.get", "products.list"],
        ),
        stop_decompose=True,
    )


def test_leaf_selects_interfaces_then_generates_with_selected_only():
    generator, client = make_generator([
        {
            "selected_interface_ids": ["products.get"],
            "selection_notes": "Need single product lookup.",
        },
        {
            "code": "def QueryProduct(product_id: int) -> dict:\n    return get_product(product_id)",
            "imports": [],
            "dependencies": [],
            "implementation_notes": "Use selected interface.",
        },
    ])
    node = make_leaf()

    code, errors = generator.generate_for_leaf(node)

    assert errors == []
    assert "get_product" in code
    assert node.granted_capabilities.granted_interfaces == ["products.get"]
    assert len(client.messages) == 2

    first_user_prompt = client.messages[0][1]["content"]
    assert "products.get" in first_user_prompt
    assert "products.list" in first_user_prompt
    assert "def get_product" not in first_user_prompt
    assert "def list_products" not in first_user_prompt

    second_user_prompt = client.messages[1][1]["content"]
    assert "def get_product(product_id: int) -> dict | None:" in second_user_prompt
    assert "def list_products" not in second_user_prompt


def test_leaf_selection_rejects_interface_outside_candidate_set():
    generator, client = make_generator([
        {
            "selected_interface_ids": ["products.delete"],
            "selection_notes": "Invalid choice.",
        },
    ])
    node = make_leaf()

    code, errors = generator.generate_for_leaf(node)

    assert code == ""
    assert len(errors) == 1
    assert errors[0].startswith("INTERFACE_SELECTION_GAP")
    assert len(client.messages) == 1
