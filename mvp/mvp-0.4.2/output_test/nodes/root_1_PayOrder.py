def PayOrder(order_id: int, user_id: int) -> Tuple[bool, str, dict]:
    try:
        order = GetOrder(order_id)
        user = GetUserAndCheckBalance(user_id, order)
        new_balance = DeductBalanceAndUpdateOrder(user, order)
        return True, "Payment successful", {"new_balance": new_balance}
    except ValueError as e:
        return False, str(e), {}