def RefundBalance(order: dict) -> dict:
    user_id = order['user_id']
    total = order['total_price']
    # Fetch current user balance (assuming update_user returns updated user or we need to get balance first)
    # Since we only have update_user, we need to assume it can handle increment or we need to read first.
    # But we don't have a read interface. So we must rely on update_user to handle the increment.
    # However, the description says update_user updates fields, so we need to pass the new balance.
    # Without a read, we cannot get current balance. This is a capability gap.
    # But the task says to refund, so we assume we can compute new balance as current_balance + total.
    # Since we cannot read current_balance, we cannot implement correctly.
    # However, the instruction says to implement using only granted interfaces.
    # We'll assume update_user can handle increment or we have to read first.
    # But we don't have read. So we'll just call update_user with a dummy increment.
    # Actually, we need to read current balance. Since not granted, we cannot.
    # But the task says 'Calls users.update(user_id, {'balance': current_balance + order['total']})'.
    # That implies we need current_balance. Without read, impossible.
    # However, maybe update_user can accept an increment operation? Not specified.
    # Given the constraints, I'll assume we can get current balance from somewhere else? No.
    # This is a capability gap. But the user expects implementation.
    # I'll implement assuming we have a get_user interface? Not granted.
    # I'll return an error dict.
    # Actually, the function signature is locked, so I must return dict.
    # I'll implement a placeholder that returns failure.
    return {'success': False, 'message': 'Cannot refund: missing read interface'}
