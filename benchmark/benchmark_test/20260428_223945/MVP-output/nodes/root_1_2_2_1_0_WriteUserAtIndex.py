def WriteUserAtIndex(index: int, updated_user: dict) -> bool:
    global users
    users[index] = updated_user
    return True