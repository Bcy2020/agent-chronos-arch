"""
Unit test: Step 2 VERIFY prompt in isolation.

Tests the code reviewer (Step 2) with multiple decomposition + code scenarios
from previous test runs. Each scenario is a standalone case — no full pipeline
needed. All LLM raw inputs and outputs are saved to tests/output/test_step2_verify/.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from api_client import APIClient
from models import Node, InputParam, OutputParam, Boundary, ChildContract, GlobalVar

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "test_step2_verify")
LLM_LOG_DIR = os.path.join(OUTPUT_DIR, "llm_log")
os.makedirs(LLM_LOG_DIR, exist_ok=True)

_call_counter = 0


class LoggingAPIClient(APIClient):
    def chat(self, messages, temperature=None, max_tokens=4096):
        global _call_counter
        _call_counter += 1
        call_id = _call_counter

        req = {
            "call_id": call_id,
            "timestamp": time.time(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        req_path = os.path.join(LLM_LOG_DIR, f"{call_id:04d}_request.json")
        with open(req_path, "w", encoding="utf-8") as f:
            json.dump(req, f, indent=2, ensure_ascii=False)

        print(f"  [LLM call #{call_id}] ...")
        start = time.time()
        response_text = super().chat(messages, temperature, max_tokens)
        elapsed = time.time() - start

        resp = {
            "call_id": call_id,
            "elapsed": round(elapsed, 2),
            "response": response_text,
        }
        resp_path = os.path.join(LLM_LOG_DIR, f"{call_id:04d}_response.json")
        with open(resp_path, "w", encoding="utf-8") as f:
            json.dump(resp, f, indent=2, ensure_ascii=False)

        print(f"    done ({elapsed:.1f}s)")
        return response_text


# ---------------------------------------------------------------------------
# New prompt builder (from step2_draft_prompt.md)
# ---------------------------------------------------------------------------

def build_verify_prompt(node: Node, code: str) -> list:
    """Build messages for Step 2 VERIFY using the new narrative prompt."""
    # Format parent inputs/outputs
    parent_inputs = ", ".join(f"{i.name}: {i.type} - {i.description}" for i in node.inputs)
    parent_outputs = ", ".join(f"{o.name}: {o.type} - {o.description}" for o in node.outputs)

    # Format children
    child_lines = []
    for child in (node.children or []):
        contract = node.children_contracts.get(child.name)
        purpose = contract.purpose if contract else child.purpose
        signature = contract.signature if contract else child.name
        child_lines.append(f"- {child.name}：{purpose}。签名：{signature}")
    children_text = "\n".join(child_lines)

    prompt = f"""有一个名为 {node.name} 的节点，其作用是：{node.purpose}。

该节点接受输入：{parent_inputs}，产生输出：{parent_outputs}。

为了实现这个节点，我们计划将其分解为以下 {len(node.children)} 个子节点：

{children_text}

现在有一份由其他开发者编写的实现代码，试图通过调用上述子节点来组合实现 {node.name}：

```python
{code}
```

请根据这份实现代码，判断上述分解是否合理。你需要从以下三个维度逐一审查：

**第一，功能覆盖：** 代码是否覆盖了 {node.name} 的全部职责？每个子节点在分解中承担的功能，是否在代码中有所体现？如果有子节点的功能被遗漏，分解就不能通过。

**第二，直接调用与树结构：** 这是一个树形分解，不是图。每个子节点必须由父节点直接调用——不能通过另一个子节点间接调用。如果代码中某个子节点没有被父节点直接调用（而是由它的兄弟节点调用），那说明分解结构有问题：要么该子节点应该成为调用它的那个子节点的下级，要么它根本不应该被分出来。

**第三，信息充分性：** 代码中不能凭空产生信息。每个函数调用的参数必须有明确来源：要么是父节点的输入，要么是之前子节点的输出，要么是常量。如果某个子节点被调用时使用了没有来源的变量，说明分解时缺少了提供该信息的子节点。

请逐项审查，给出判定结果。如果任意一项不通过，返回 cannot_compose 并说明原因和修复建议；如果全部通过，返回 ok。

返回合法 JSON，格式如下：
{{
  "status": "ok 或 cannot_compose",
  "checks": {{
    "function_coverage": {{"passed": true/false, "reason": "通过原因或失败原因"}},
    "direct_calls": {{"passed": true/false, "reason": "通过原因或失败原因"}},
    "information_sufficiency": {{"passed": true/false, "reason": "通过原因或失败原因"}}
  }},
  "failed_checks": ["未通过的检查项名称"],
  "suggested_fix": "修复建议（仅 cannot_compose 时需要）"
}}"""

    return [{"role": "user", "content": prompt}]


# ---------------------------------------------------------------------------
# Scenario builders
# ---------------------------------------------------------------------------

def make_node(name, purpose, inputs, outputs, children, contracts=None):
    """Helper to construct a Node with children and contracts."""
    node = Node(
        node_id="test",
        name=name,
        depth=0,
        purpose=purpose,
        inputs=[InputParam(name=n, type=t, description=d) for n, t, d in inputs],
        outputs=[OutputParam(name=n, type=t, description=d) for n, t, d in outputs],
        boundary=Boundary(in_scope=[], out_of_scope=[]),
    )
    node.children = children
    node.children_contracts = contracts or {}
    return node


def child(name, purpose, signature, stop=True):
    """Helper to create a child Node."""
    c = Node(
        node_id=f"test_{name}",
        name=name,
        depth=1,
        purpose=purpose,
        inputs=[], outputs=[],
        boundary=Boundary(in_scope=[], out_of_scope=[]),
    )
    c.stop_decompose = stop
    return c, ChildContract(
        purpose=purpose,
        inputs=[], outputs=[],
        behavior=purpose,
        signature=signature,
    )


# ---------------------------------------------------------------------------
# Scenarios from previous test runs
# ---------------------------------------------------------------------------

def scenario_order_flat_dispatch():
    """order_prd: flat dispatch with RouteCommand — should REJECT (direct_calls)."""
    children_list = []
    contracts = {}
    for name, purpose, sig in [
        ("ParseInput", "Parse input JSON into command and order_data", "def ParseInput(input: Any) -> Tuple[str, dict]"),
        ("RouteCommand", "Route command to appropriate handler", "def RouteCommand(command: str, order_data: dict) -> dict"),
        ("CreateOrderHandler", "Handle create_order: validate user, check stock, create order", "def CreateOrderHandler(order_data: dict) -> dict"),
        ("PayOrderHandler", "Handle pay_order: check order, deduct balance, update status", "def PayOrderHandler(order_data: dict) -> dict"),
        ("ShipOrderHandler", "Handle ship_order: check order is paid, update status to shipped", "def ShipOrderHandler(order_data: dict) -> dict"),
        ("CompleteOrderHandler", "Handle complete_order: check order is shipped, update status", "def CompleteOrderHandler(order_data: dict) -> dict"),
        ("CancelOrderHandler", "Handle cancel_order: check order, restore stock, refund", "def CancelOrderHandler(order_data: dict) -> dict"),
        ("ListOrdersHandler", "Handle list_orders: list orders with filters", "def ListOrdersHandler(order_data: dict) -> dict"),
        ("GetUserOrdersHandler", "Handle get_user_orders: get orders for a user", "def GetUserOrdersHandler(order_data: dict) -> dict"),
        ("ListProductsHandler", "Handle list_products: list products with optional filter", "def ListProductsHandler(order_data: dict) -> dict"),
    ]:
        c, ct = child(name, purpose, sig)
        children_list.append(c)
        contracts[name] = ct

    node = make_node(
        "Order_prd", "An order management system that coordinates users, products, and orders",
        [("input", "Any", "System input")], [("output", "Any", "System output")],
        children_list, contracts
    )

    code = """def Order_prd(input: Any) -> Any:
    command, order_data = ParseInput(input)
    result = RouteCommand(command, order_data)
    return result"""

    return node, code, "reject", "direct_calls"


def scenario_order_direct_dispatch():
    """order_prd: parent directly calls all handlers — should PASS."""
    children_list = []
    contracts = {}
    for name, purpose, sig in [
        ("CreateOrder", "Handle create_order: validate user, check stock, create order", "def CreateOrder(order_data: dict) -> dict"),
        ("PayOrder", "Handle pay_order: check order, deduct balance, update status", "def PayOrder(order_data: dict) -> dict"),
        ("ShipOrder", "Handle ship_order: check order is paid, update status to shipped", "def ShipOrder(order_data: dict) -> dict"),
        ("CompleteOrder", "Handle complete_order: check order is shipped, update status", "def CompleteOrder(order_data: dict) -> dict"),
        ("CancelOrder", "Handle cancel_order: check order, restore stock, refund", "def CancelOrder(order_data: dict) -> dict"),
        ("ListOrders", "Handle list_orders: list orders with filters", "def ListOrders(order_data: dict) -> dict"),
        ("GetUserOrders", "Handle get_user_orders: get orders for a user", "def GetUserOrders(order_data: dict) -> dict"),
        ("ListProducts", "Handle list_products: list products with optional filter", "def ListProducts(order_data: dict) -> dict"),
    ]:
        c, ct = child(name, purpose, sig)
        children_list.append(c)
        contracts[name] = ct

    node = make_node(
        "Order_prd", "An order management system that coordinates users, products, and orders",
        [("input", "Any", "System input")], [("output", "Any", "System output")],
        children_list, contracts
    )

    code = """def Order_prd(input: Any) -> Any:
    command = input.get('command')
    order_data = input.get('order_data', {})
    if command == 'create_order':
        return CreateOrder(order_data)
    elif command == 'pay_order':
        return PayOrder(order_data)
    elif command == 'ship_order':
        return ShipOrder(order_data)
    elif command == 'complete_order':
        return CompleteOrder(order_data)
    elif command == 'cancel_order':
        return CancelOrder(order_data)
    elif command == 'list_orders':
        return ListOrders(order_data)
    elif command == 'get_user_orders':
        return GetUserOrders(order_data)
    elif command == 'list_products':
        return ListProducts(order_data)
    else:
        return {'success': False, 'message': 'Unknown command'}"""

    return node, code, "pass", "all"


def scenario_grade_flat_dispatch():
    """grade_prd: flat dispatch with RouteCommand — should REJECT (direct_calls)."""
    children_list = []
    contracts = {}
    for name, purpose, sig in [
        ("ParseInput", "Parse input JSON into command and grade_data", "def ParseInput(input: Any) -> Tuple[str, dict]"),
        ("RouteCommand", "Route command to appropriate handler", "def RouteCommand(command: str, grade_data: dict) -> dict"),
        ("HandleRecordGrade", "Handle record_grade: record a student's grade", "def HandleRecordGrade(grade_data: dict) -> dict"),
        ("HandleUpdateGrade", "Handle update_grade: update an existing grade", "def HandleUpdateGrade(grade_data: dict) -> dict"),
        ("HandleDeleteGrade", "Handle delete_grade: delete a grade record", "def HandleDeleteGrade(grade_data: dict) -> dict"),
        ("HandleGetStudentGrades", "Handle get_student_grades: get all grades for a student", "def HandleGetStudentGrades(grade_data: dict) -> dict"),
        ("HandleGetCourseGrades", "Handle get_course_grades: get all grades for a course", "def HandleGetCourseGrades(grade_data: dict) -> dict"),
        ("HandleListClassGrades", "Handle list_class_grades: list grades for a class", "def HandleListClassGrades(grade_data: dict) -> dict"),
        ("HandleGetGradeReport", "Handle get_grade_report: generate grade report", "def HandleGetGradeReport(grade_data: dict) -> dict"),
        ("HandleGetCourseStats", "Handle get_course_stats: get statistics for a course", "def HandleGetCourseStats(grade_data: dict) -> dict"),
        ("HandleAddStudent", "Handle add_student: add a new student", "def HandleAddStudent(grade_data: dict) -> dict"),
        ("HandleAddCourse", "Handle add_course: add a new course", "def HandleAddCourse(grade_data: dict) -> dict"),
    ]:
        c, ct = child(name, purpose, sig)
        children_list.append(c)
        contracts[name] = ct

    node = make_node(
        "Grade_prd", "A student grade management system",
        [("input", "Any", "System input")], [("output", "Any", "System output")],
        children_list, contracts
    )

    code = """def Grade_prd(input: Any) -> Any:
    command, grade_data = ParseInput(input)
    result = RouteCommand(command, grade_data)
    return result"""

    return node, code, "reject", "direct_calls"


def scenario_project_flat_dispatch():
    """project_prd: flat dispatch with RouteCommand — should REJECT (direct_calls)."""
    children_list = []
    contracts = {}
    for name, purpose, sig in [
        ("ParseInput", "Parse input JSON into command and project_data", "def ParseInput(input: Any) -> Tuple[str, dict]"),
        ("RouteCommand", "Route command to appropriate handler", "def RouteCommand(command: str, project_data: dict) -> dict"),
        ("HandleProjectCommands", "Handle project commands: create, list, update projects", "def HandleProjectCommands(project_data: dict) -> dict"),
        ("HandleTaskCommands", "Handle task commands: create, assign, update tasks", "def HandleTaskCommands(project_data: dict) -> dict"),
        ("HandleQueryCommands", "Handle query commands: get status, get stats", "def HandleQueryCommands(project_data: dict) -> dict"),
        ("HandleMemberCommands", "Handle member commands: add, remove, list members", "def HandleMemberCommands(project_data: dict) -> dict"),
    ]:
        c, ct = child(name, purpose, sig)
        children_list.append(c)
        contracts[name] = ct

    node = make_node(
        "Project_prd", "A project task management system",
        [("input", "Any", "System input")], [("output", "Any", "System output")],
        children_list, contracts
    )

    code = """def Project_prd(input: Any) -> Any:
    command, project_data = ParseInput(input)
    result = RouteCommand(command, project_data)
    return result"""

    return node, code, "reject", "direct_calls"


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

SCENARIOS = [
    ("order_flat_dispatch", scenario_order_flat_dispatch),
    ("order_direct_dispatch", scenario_order_direct_dispatch),
    ("grade_flat_dispatch", scenario_grade_flat_dispatch),
    ("project_flat_dispatch", scenario_project_flat_dispatch),
]


def run_scenario(api_client, name, builder_fn):
    node, code, expected_verdict, expected_check = builder_fn()

    print(f"\n{'='*60}")
    print(f"  Scenario: {name}")
    print(f"  Children: {len(node.children)}")
    print(f"  Expected: {expected_verdict} (check: {expected_check})")
    print(f"{'='*60}")

    messages = build_verify_prompt(node, code)

    # Save the prompt for inspection
    prompt_path = os.path.join(OUTPUT_DIR, f"{name}_prompt.txt")
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(messages[0]["content"])

    response_text = api_client.chat(messages, temperature=0.2, max_tokens=1024)

    # Parse response
    try:
        resp = json.loads(response_text.strip().strip("```json").strip("```"))
    except json.JSONDecodeError:
        print(f"  PARSE ERROR: {response_text[:200]}")
        return {"scenario": name, "verdict": "parse_error", "raw": response_text}

    status = resp.get("status", "unknown")
    checks = resp.get("checks", {})
    failed_checks = resp.get("failed_checks", [])
    suggested_fix = resp.get("suggested_fix", "")

    # Print results
    passed = "PASS" if status == "ok" else "REJECT"
    print(f"  Verdict: {passed} (status={status})")
    for check_name, check_data in checks.items():
        p = "PASS" if check_data.get("passed") else "FAIL"
        reason = check_data.get("reason", "")
        print(f"    {check_name}: [{p}] {reason[:120]}")
    if failed_checks:
        print(f"  Failed checks: {failed_checks}")
    if suggested_fix:
        print(f"  Suggested fix: {suggested_fix[:200]}")

    # Check if result matches expectation
    if expected_verdict == "reject" and status == "ok":
        print(f"  MISMATCH: expected REJECT but got ok")
    elif expected_verdict == "reject_literal_return" and status == "ok":
        print(f"  MISMATCH: expected REJECT (literal return) but got ok")
    elif expected_verdict == "pass" and status == "cannot_compose":
        print(f"  MISMATCH: expected ok but got cannot_compose")
    else:
        print(f"  MATCH: result matches expectation")

    return {
        "scenario": name,
        "verdict": status,
        "expected": expected_verdict,
        "checks": checks,
        "failed_checks": failed_checks,
        "suggested_fix": suggested_fix,
    }


def main():
    cfg = Config(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        temperature=0.2,
    )
    if not cfg.api_key:
        print("ERROR: DEEPSEEK_API_KEY not set")
        sys.exit(1)

    api_client = LoggingAPIClient(cfg)

    results = []
    for name, builder in SCENARIOS:
        result = run_scenario(api_client, name, builder)
        results.append(result)

    # Summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    for r in results:
        exp = r["expected"]
        got = r["verdict"]
        match = (
            (exp == "reject" and got == "cannot_compose") or
            (exp == "reject_literal_return" and got == "cannot_compose") or
            (exp == "pass" and got == "ok")
        )
        mark = "MATCH" if match else "MISMATCH"
        print(f"  [{mark}] {r['scenario']:30s} expected={exp:20s} got={got}")

    # Save results
    result_path = os.path.join(OUTPUT_DIR, "results.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  Results: {result_path}")
    print(f"  LLM log: {LLM_LOG_DIR}")

    mismatches = sum(1 for r in results if not (
        (r["expected"] == "reject" and r["verdict"] == "cannot_compose") or
        (r["expected"] == "reject_literal_return" and r["verdict"] == "cannot_compose") or
        (r["expected"] == "pass" and r["verdict"] == "ok")
    ))
    if mismatches:
        print(f"\n  {mismatches} SCENARIO(S) MISMATCHED")
        return 1
    else:
        print(f"\n  ALL SCENARIOS MATCHED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
