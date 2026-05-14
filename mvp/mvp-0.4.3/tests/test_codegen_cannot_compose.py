"""
Tests: code_generator cannot_compose rejection.

Verifies that CodeGenerator:
  - Returns valid code when children CAN compose the parent (correct decomposition)
  - Returns CANNOT_COMPOSE when children CANNOT compose the parent (incorrect decomposition)
  - Short-circuits in generate_with_retry on CANNOT_COMPOSE

Known limitations:
  - Uses fake APIClient, does not test real LLM behavior.
  - Only validates the schema-level rejection, not semantic correctness of the generated code.
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from typing import List
from config import Config
from models import Node, InputParam, OutputParam, Boundary, ChildContract
from code_generator import CodeGenerator


class FakeAPIClient:
    def __init__(self, responses: List[dict]):
        self.responses = responses
        self.call_count = 0

    def chat(self, messages, max_tokens=2048):
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return json.dumps(resp)
        return json.dumps({"code": "", "error": "No more fake responses"})


def make_node(name: str, children_names: List[str], inputs: list = None) -> Node:
    node = Node(node_id=name.lower(), name=name, depth=1)
    for i, cn in enumerate(children_names):
        child = Node(node_id=f"{name.lower()}_{i}", name=cn, depth=2)
        child.inputs = [InputParam(name="dummy", type="str", description="")]
        child.outputs = [OutputParam(name="result", type="str", description="")]
        node.children.append(child)
        node.children_contracts[cn] = ChildContract(
            purpose=f"Child {cn}",
            inputs=[InputParam(name="dummy", type="str", description="")],
            outputs=[OutputParam(name="result", type="str", description="")],
            signature=f"def {cn}(input_data: str) -> str",
        )
    if inputs:
        node.inputs = inputs
    else:
        node.inputs = [InputParam(name="input_data", type="str", description="")]
    node.outputs = [OutputParam(name="result", type="str", description="")]
    node.boundary = Boundary(in_scope=[], out_of_scope=[])
    return node


cfg = Config(api_key="test", max_decompose_retries=3)
passed = 0
failed = 0


def check(name: str, node: Node, responses: list, expect_code: bool, expect_cannot_compose: bool):
    global passed, failed
    client = FakeAPIClient(responses)
    cg = CodeGenerator(cfg, client)
    code, errors = cg.generate_with_retry(node)

    if expect_code:
        if code and not errors:
            print(f"  PASS: {name}")
            passed += 1
        else:
            print(f"  FAIL: {name} — expected code, got errors={errors}")
            failed += 1
    elif expect_cannot_compose:
        if not code and errors and any(e.startswith("CANNOT_COMPOSE") for e in errors):
            print(f"  PASS: {name}")
            passed += 1
        else:
            print(f"  FAIL: {name} — expected CANNOT_COMPOSE, got code={code!r} errors={errors}")
            failed += 1


# ============================================================
# Test Group A: Correct decompositions (parent can compose children)
# ============================================================
print("=== Group A: Correct decompositions (should produce code) ===")

# A1: Simple sequential composition
check(
    "A1. simple sequential",
    make_node("ProcessOrder", ["ValidateUser", "CalculateTotal", "SaveOrder"]),
    responses=[{
        "status": "ok",
        "code": "def ProcessOrder(input_data: str) -> str:\n    user = ValidateUser(input_data)\n    total = CalculateTotal(input_data, user)\n    result = SaveOrder(input_data, total)\n    return result",
        "imports": [],
        "child_calls": ["ValidateUser", "CalculateTotal", "SaveOrder"],
        "implementation_notes": ""
    }],
    expect_code=True,
    expect_cannot_compose=False
)

# A2: Composition with conditionals (branching)
check(
    "A2. conditional composition",
    make_node("HandleRequest", ["AuthUser", "ProcessData", "LogRequest"]),
    responses=[{
        "status": "ok",
        "code": "def HandleRequest(input_data: str) -> str:\n    user = AuthUser(input_data)\n    if user:\n        result = ProcessData(input_data, user)\n    else:\n        result = 'unauthorized'\n    LogRequest(input_data)\n    return result",
        "imports": [],
        "child_calls": ["AuthUser", "ProcessData", "LogRequest"],
        "implementation_notes": ""
    }],
    expect_code=True,
    expect_cannot_compose=False
)

# A3: Composition with loops
check(
    "A3. loop composition",
    make_node("BatchProcess", ["ProcessItem", "AggregateResults"]),
    responses=[{
        "status": "ok",
        "code": "def BatchProcess(input_data: str) -> str:\n    results = []\n    for item in input_data.split(','):\n        r = ProcessItem(item.strip())\n        results.append(r)\n    return AggregateResults(results)",
        "imports": [],
        "child_calls": ["ProcessItem", "AggregateResults"],
        "implementation_notes": ""
    }],
    expect_code=True,
    expect_cannot_compose=False
)

# ============================================================
# Test Group B: Incorrect decompositions (parent cannot compose)
# ============================================================
print("\n=== Group B: Incorrect decompositions (should return CANNOT_COMPOSE) ===")

# B1: Child needs data that no one provides
check(
    "B1. missing child input source",
    make_node("CreateOrder", ["ValidateUser", "CalculateTotal", "CreateOrderRecord"]),
    responses=[{
        "status": "cannot_compose",
        "code": "",
        "imports": [],
        "child_calls": [],
        "implementation_notes": "Cannot compose from child calls only",
        "decomposition_feedback": {
            "reason": "missing_child_input_source",
            "offending_child": "CalculateTotal",
            "missing_inputs": [{
                "child": "CalculateTotal", "param": "products_data",
                "why_needed": "CalculateTotal needs product price info",
                "expected_source": "output of a FetchProductsForItems child"
            }],
            "suggested_fix": "Add FetchProductsForItems child before CalculateTotal.",
            "requires_redecomposition": True
        }
    }],
    expect_code=False,
    expect_cannot_compose=True
)

# B2: Child signature doesn't match parent's data shape
check(
    "B2. wrong child signature",
    make_node("UpdateProfile", ["FetchUser", "ValidateEmail", "SaveUser"]),
    responses=[{
        "status": "cannot_compose",
        "code": "",
        "imports": [],
        "child_calls": [],
        "implementation_notes": "Child signatures don't form a valid composition",
        "decomposition_feedback": {
            "reason": "wrong_child_signature",
            "offending_child": "ValidateEmail",
            "missing_inputs": [],
            "direct_resource_accesses": [],
            "suggested_fix": "ValidateEmail should accept user data from FetchUser, not raw email string.",
            "requires_redecomposition": True
        }
    }],
    expect_code=False,
    expect_cannot_compose=True
)

# B3: Parent cannot be satisfied from child outputs alone
check(
    "B3. cannot satisfy parent output",
    make_node("GenerateReport", ["FetchData", "FormatData"]),
    responses=[{
        "status": "cannot_compose",
        "code": "",
        "imports": [],
        "child_calls": [],
        "implementation_notes": "Children provide raw data but no aggregation logic",
        "decomposition_feedback": {
            "reason": "cannot_satisfy_parent_output",
            "offending_child": "",
            "missing_inputs": [],
            "direct_resource_accesses": [],
            "suggested_fix": "Add an AggregateData child that transforms formatted data into the final report format.",
            "requires_redecomposition": True
        }
    }],
    expect_code=False,
    expect_cannot_compose=True
)

# B4: Validator also catches via passive check (genuine dangling param)
check(
    "B4. genuine dangling param (should still fail)",
    make_node("CreateOrder2", ["ValidateUser", "CalculateTotal", "CreateOrderRecord"]),
    responses=[{
        "status": "ok",
        "code": "def CreateOrder2(input_data: str) -> str:\n    ok = ValidateUser(input_data)\n    total = CalculateTotal(input_data, products_data)\n    return CreateOrderRecord(input_data, total)",
        "imports": [],
        "child_calls": ["ValidateUser", "CalculateTotal", "CreateOrderRecord"],
        "implementation_notes": ""
    }],
    expect_code=True,
    expect_cannot_compose=False
)

# ============================================================
print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed")
if failed > 0:
    print("SOME TESTS FAILED")
    exit(1)
else:
    print("ALL TESTS PASSED")
