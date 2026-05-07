def RefundBalance(order: dict, is_paid: bool) -> Tuple[bool, str]:
    if not CheckIfPaid(is_paid):
        return True, ''
    user_id = order['user_id']
    try:
        user = GetUser(user_id)
    except Exception as e:
        return False, str(e)
    total = order['total_price']
    new_balance = ComputeNewBalance(user, total)
    success, error = UpdateUserBalance(user_id, new_balance)
    return success, error