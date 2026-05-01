def IterateAndMatch(updated_user: dict) -> int:
    global users
    for index, user in enumerate(users):
        if user['id'] == updated_user['id']:
            return index
    return -1