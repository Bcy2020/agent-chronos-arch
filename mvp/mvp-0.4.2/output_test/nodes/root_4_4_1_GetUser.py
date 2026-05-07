def GetUser(user_id: int) -> dict:
    user = get_user(user_id)
    if user is None:
        raise ValueError(f"User with id {user_id} not found")
    return user