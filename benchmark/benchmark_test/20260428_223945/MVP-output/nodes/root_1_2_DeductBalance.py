def DeductBalance(user_id: int, total_amount: float) -> bool:
    user = FindUser(user_id)
    updated_user = DeductBalanceFromUser(user, total_amount)
    success = UpdateUserInStore(updated_user)
    return success