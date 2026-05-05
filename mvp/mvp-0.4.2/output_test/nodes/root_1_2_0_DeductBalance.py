def DeductBalance(user: dict, order: dict) -> float:
    new_balance = ComputeNewBalance(user, order)
    UpdateUserBalance(user['user_id'], new_balance)
    return new_balance