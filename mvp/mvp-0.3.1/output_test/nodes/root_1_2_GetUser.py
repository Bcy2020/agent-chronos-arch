def GetUser(user_id: int) -> dict:
    for user in users:
        if user.get('id') == user_id:
            return user
    return None