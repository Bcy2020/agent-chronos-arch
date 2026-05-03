def ValidateUser(user_id: int) -> bool:
    # Access the global users list
    global users
    # Iterate through users to find matching user_id
    for user in users:
        if user.get('user_id') == user_id:
            return True
    return False