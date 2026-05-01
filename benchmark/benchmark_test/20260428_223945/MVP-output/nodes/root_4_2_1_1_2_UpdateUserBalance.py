def UpdateUserBalance(user: dict, total: float) -> bool:
    user['balance'] = user.get('balance', 0.0) + total
    for i, u in enumerate(users):
        if u['id'] == user['id']:
            users[i] = user
            break
    return True