def CheckBalance(user: dict, order: dict) -> dict:
    if user is None:
        raise ValueError('User not found')
    if user['balance'] < order['total_price']:
        raise ValueError('Insufficient balance')
    return user