def GetUserAndCheckBalance(user_id: int, order: dict) -> dict:
    user = GetUser(user_id)
    return CheckBalance(user, order)