def UpdateUserBalance(user: dict, new_balance: float) -> dict:
    user_id = user['user_id']
    updates = {'balance': new_balance}
    updated_user = update_user(user_id, updates)
    return updated_user