def FindUserById(user_id: int) -> Optional[dict]:
    global users
    for user in users:
        if user.get('user_id') == user_id:
            return user
    return None