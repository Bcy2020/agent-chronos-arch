"""
Tests: validate_child_input_provenance with real-world code patterns.

Verifies that the provenance checker correctly:
  - PASSES legitimate parent orchestration (for-loops, try-blocks, if/else, with-statements)
  - FAILS genuinely dangling parameters that have no source

Known limitations:
  - Does not track variables across function call boundaries
  - Does not handle comprehensions, closures, nested functions
  - Conservative: may miss some edge cases (e.g., try/except with complex control flow)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from models import Node
from validator import Validator

cfg = Config(api_key="test")
val = Validator(cfg)
passed = 0
failed = 0


def check(name, node, code, expect_pass):
    global passed, failed
    ok, errs = val.validate_child_input_provenance(node, code)
    if ok == expect_pass:
        status = "PASS"
        passed += 1
    else:
        status = "FAIL"
        failed += 1
    detail = f" ({len(errs)} errors)" if errs else ""
    print(f"  {status}: {name}{detail}")
    if not ok and not expect_pass:
        for e in errs:
            print(f"    {e}")


# --- Group A: Legitimate parent orchestration (should PASS) ---
print("=== Group A: Legitimate coordination (should pass) ===")

check("A1. for-loop tuple unpacking",
      Node("", "CheckStockSufficiency", 1, children=[Node("", "CheckStockForItem", 2), Node("", "AggregateValidatedItems", 2)]),
      """def CheckStockSufficiency(items: list, product_details: list) -> list:
    validated = []
    for item, product in zip(items, product_details):
        result = CheckStockForItem(item, product)
        validated.append(result)
    return AggregateValidatedItems(validated)""",
      expect_pass=True)

check("A2. for-loop derived vars",
      Node("", "DeductStock", 1, children=[Node("", "GetProductStock", 2), Node("", "UpdateProductStock", 2)]),
      """def DeductStock(items: list) -> bool:
    for item in items:
        pid = item['product_id']
        qty = item['quantity']
        stock = GetProductStock(pid)
        if stock < qty:
            return False
        UpdateProductStock(pid, qty, stock)
    return True""",
      expect_pass=True)

check("A3. try-block child output",
      Node("", "CompleteOrder", 1, children=[Node("", "GetOrder", 2), Node("", "ValidateOrderStatus", 2), Node("", "UpdateOrderStatus", 2)]),
      """def CompleteOrder(order_data: dict) -> dict:
    try:
        order = GetOrder(order_data)
        if not ValidateOrderStatus(order):
            return {"success": False}
        UpdateOrderStatus(order_data["order_id"])
        return {"success": True}
    except Exception as e:
        return {"success": False, "message": str(e)}""",
      expect_pass=True)

check("A4. try-block multi-child chain",
      Node("", "CancelOrder", 1, children=[Node("", "GetOrder", 2), Node("", "ValidateOrderStatus", 2),
                                           Node("", "RestoreStock", 2), Node("", "RefundBalance", 2),
                                           Node("", "UpdateOrderStatus", 2)]),
      """def CancelOrder(order_data: dict) -> dict:
    try:
        order = GetOrder(order_data)
        is_valid, status = ValidateOrderStatus(order)
        if not is_valid:
            return {"success": False}
        RestoreStock(order)
        RefundBalance(order, status)
        UpdateOrderStatus(order)
        return {"success": True}
    except Exception as e:
        return {"success": False, "message": str(e)}""",
      expect_pass=True)

check("A5. if/else branching",
      Node("", "ShipOrder", 1, children=[Node("", "GetOrder", 2), Node("", "UpdateOrderStatus", 2)]),
      """def ShipOrder(order_data: dict) -> dict:
    order = GetOrder(order_data)
    if order["status"] == "paid":
        result = UpdateOrderStatus(order_data)
    else:
        result = None
    return result""",
      expect_pass=True)

check("A6. with-statement binding",
      Node("", "ReadFile", 1, children=[Node("", "ProcessContent", 2)]),
      """def ReadFile(path: str) -> str:
    with open(path) as f:
        data = ProcessContent(f)
    return data""",
      expect_pass=True)

check("A7. try/except handler variable",
      Node("", "SafeProcess", 1, children=[Node("", "DoWork", 2)]),
      """def SafeProcess(input_data: str) -> str:
    try:
        return DoWork(input_data)
    except Exception as e:
        return f"error: {e}" """,
      expect_pass=True)


# --- Group B: Genuinely dangling parameters (should FAIL) ---
print("\n=== Group B: Genuinely missing inputs (should fail) ===")

check("B1. dangling products_data",
      Node("", "CreateOrder", 1, children=[Node("", "ValidateUser", 2), Node("", "CalculateTotal", 2), Node("", "CreateOrderRecord", 2)]),
      """def CreateOrder(user_id: int, items: list) -> dict:
    ok = ValidateUser(user_id)
    total = CalculateTotal(items, products_data)
    return CreateOrderRecord(user_id, items, total)""",
      expect_pass=False)

check("B2. missing sibling output",
      Node("", "BuildReport", 1, children=[Node("", "FetchRawData", 2), Node("", "ComputeStats", 2)]),
      """def BuildReport(source: str) -> dict:
    raw = FetchRawData(source)
    stats = ComputeStats(raw, threshold)
    return {"raw": raw, "stats": stats}""",
      expect_pass=False)


# --- Summary ---
print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed")
if failed > 0:
    print("SOME TESTS FAILED")
    exit(1)
else:
    print("ALL TESTS PASSED")
