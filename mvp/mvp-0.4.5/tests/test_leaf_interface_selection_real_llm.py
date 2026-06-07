"""
Real LLM smoke test for leaf interface selection.

This script validates the MVP 0.4.5 two-step leaf flow with a real API call:
  1. Select concrete interfaces from candidate interfaces.
  2. Generate code using only the selected interface definitions.

Run directly:
  python tests/test_leaf_interface_selection_real_llm.py
"""
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_client import APIClient
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


OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__),
    "output",
    "test_leaf_interface_selection_real_llm",
)


class RecordingAPIClient:
    def __init__(self, delegate):
        self.delegate = delegate
        self.calls = []

    def chat(self, messages, temperature=None, max_tokens=4096):
        started = time.time()
        response = self.delegate.chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self.calls.append({
            "messages": messages,
            "response": response,
            "elapsed_seconds": time.time() - started,
            "max_tokens": max_tokens,
        })
        return response


def make_interface_plan():
    return InterfacePlan(
        resources=[],
        interfaces=[
            InterfaceSpec(
                interface_id="products.get",
                resource_id="products",
                operation="get",
                function_name="get_product",
                signature="def get_product(product_id: int) -> dict | None:",
                description="Retrieve exactly one product by product_id.",
            ),
            InterfaceSpec(
                interface_id="products.list",
                resource_id="products",
                operation="list",
                function_name="list_products",
                signature="def list_products(category: str | None = None) -> list[dict]:",
                description="List or search multiple products.",
            ),
        ],
    )


def make_leaf_node():
    return Node(
        node_id="leaf_real_llm_1",
        name="QueryProduct",
        depth=2,
        purpose="Return exactly one product by id.",
        inputs=[InputParam("product_id", "int", "Product id")],
        outputs=[OutputParam("product", "dict", "Product row")],
        boundary=Boundary(
            in_scope=["read one product by id"],
            out_of_scope=["list multiple products", "update products"],
        ),
        requested_capabilities=["products.read"],
        granted_capabilities=CapabilityGrant(
            node_id="leaf_real_llm_1",
            candidate_interfaces=["products.get", "products.list"],
        ),
        stop_decompose=True,
        stop_reason="real LLM smoke test leaf",
    )


def run():
    cfg = Config.from_env()
    cfg.temperature = 0.0
    cfg.max_retries = 1

    if not cfg.api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set.")

    recorder = RecordingAPIClient(APIClient(cfg))
    generator = CodeGenerator(cfg, recorder)
    generator.set_interface_plan(make_interface_plan())

    node = make_leaf_node()
    code, errors = generator.generate_for_leaf(node)

    selected = node.granted_capabilities.granted_interfaces
    first_user_prompt = recorder.calls[0]["messages"][1]["content"] if recorder.calls else ""
    second_user_prompt = recorder.calls[1]["messages"][1]["content"] if len(recorder.calls) > 1 else ""
    result = {
        "timestamp": datetime.now().isoformat(),
        "model": cfg.model,
        "base_url": cfg.base_url,
        "selected_interfaces": selected,
        "code": code,
        "errors": errors,
        "calls": recorder.calls,
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(
        OUTPUT_DIR,
        f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    assertions = [
        (len(recorder.calls) == 2, "expected exactly two LLM calls"),
        (errors == [], f"expected no errors, got {errors}"),
        (selected == ["products.get"], f"expected ['products.get'], got {selected}"),
        ("get_product" in code, "generated code should call get_product"),
        ("list_products" not in code, "generated code must not call list_products"),
        ("products.get" in first_user_prompt, "first prompt should include products.get candidate id"),
        ("products.list" in first_user_prompt, "first prompt should include products.list candidate id"),
        ("def get_product" not in first_user_prompt, "first prompt should not include selected full signature"),
        ("def list_products" not in first_user_prompt, "first prompt should not include unselected full signature"),
        ("def get_product(product_id: int) -> dict | None:" in second_user_prompt,
         "second prompt should include selected full signature"),
        ("def list_products" not in second_user_prompt,
         "second prompt must not include unselected full signature"),
    ]
    failures = [message for ok, message in assertions if not ok]

    print("=" * 70)
    print("REAL LLM LEAF INTERFACE SELECTION SMOKE TEST")
    print("=" * 70)
    print(f"model: {cfg.model}")
    print(f"selected_interfaces: {selected}")
    print(f"errors: {errors}")
    print(f"calls: {len(recorder.calls)}")
    print(f"output: {output_path}")
    print()
    print(code)
    print()

    if failures:
        print("FAIL")
        for failure in failures:
            print(f"  - {failure}")
        raise SystemExit(1)

    print("PASS")


if __name__ == "__main__":
    run()
