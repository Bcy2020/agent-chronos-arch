def CheckBalance(user: dict, order: dict) -> bool:
    if user is None or order is None:
        return False
    return user.get('balance', 0) >= order.get('total_price', 0)