def CheckBalance(user: dict, order: dict) -> bool:
    return user.get('balance', 0) >= order.get('total_price', 0)