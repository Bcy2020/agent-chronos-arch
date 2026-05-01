def FetchUserBalance(user_id: int) -> float:
    # Access the global users list
    global users
    # Search for the user with matching user_id
    for user in users:
        if user['id'] == user_id:
            return float(user['balance'])
    # If not found, return 0.0
    return 0.0