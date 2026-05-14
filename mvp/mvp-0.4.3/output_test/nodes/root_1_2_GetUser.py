def GetUser(order: dict) -> dict:
    user_id = ExtractUserId(order)
    user = GetUserFromStore(user_id)
    if user is None:
        raise ValueError(f"User with id {user_id} not found")
    return user