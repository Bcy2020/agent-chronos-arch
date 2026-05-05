def UpdateUserBalance(user: dict, total: float) -> bool:
    try:
        new_balance = user['balance'] + total
        update_user(user['id'], {'balance': new_balance})
        return True
    except Exception:
        return False