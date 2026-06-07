def CalculateBill(items: list) -> dict:
    # BAD: calls CalculateTotal but ignores result, returns literal
    calc_result = CalculateTotal(items)
    return {"total": 0.0}
