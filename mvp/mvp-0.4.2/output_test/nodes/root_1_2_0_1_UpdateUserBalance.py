def UpdateUserBalance(user_id: int, new_balance: float) -> None:
    update_user(user_id, {'balance': new_balance})