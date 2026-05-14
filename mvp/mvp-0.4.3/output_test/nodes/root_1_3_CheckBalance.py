def CheckBalance(user: dict, order: dict) -> bool:
    return user['balance'] >= order['total_price']