def IterateAndFindUser(user_id: int, users: list) -> dict:
    for user in users:
        if user.get('id') == user_id:
            return user
    return None