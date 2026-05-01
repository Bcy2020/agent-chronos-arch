def FindUser(user_id: int) -> dict:
    user = SearchUsersList(user_id)
    if user is None:
        raise ValueError(f"User with id {user_id} not found")
    return user