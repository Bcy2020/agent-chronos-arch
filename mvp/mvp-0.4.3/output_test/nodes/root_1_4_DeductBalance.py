def DeductBalance(user: dict, order: dict) -> dict:
    new_balance = ComputeNewBalance(user, order)
    updated_user = UpdateUserBalance(user, new_balance)
    return updated_user