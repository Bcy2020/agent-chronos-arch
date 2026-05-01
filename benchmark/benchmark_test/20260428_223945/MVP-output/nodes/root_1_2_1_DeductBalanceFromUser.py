def DeductBalanceFromUser(user: dict, total_amount: float) -> dict:
    updated_user = user.copy()
    updated_user['balance'] -= total_amount
    return updated_user