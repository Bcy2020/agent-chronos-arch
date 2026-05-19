def GetUser(order: dict) -> dict:
    user_id = order['user_id']
    user = get_user(user_id)
    return user