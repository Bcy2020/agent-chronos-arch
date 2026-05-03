def DeductBalance(user_id: int, amount: float) -> bool:
    global users
    for user in users:
        if user['id'] == user_id:
            user['balance'] -= amount
            return True
    return False