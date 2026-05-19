def DeductBalance(user: dict, order: dict) -> dict:
    new_balance = user['balance'] - order['total_price']
    updated_user = update_user(user['user_id'], {'balance': new_balance})
    return updated_user