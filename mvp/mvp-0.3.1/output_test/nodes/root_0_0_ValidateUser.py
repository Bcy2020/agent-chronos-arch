def ValidateUser(user_id: int) -> bool:
    # Access the global users list
    global users
    # Check if any user has the given user_id
    for user in users:
        if user.get('user_id') == user_id:
            return True
    return False