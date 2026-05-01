def FilterOrdersByUser(user_id: int, orders: list) -> list:
    return [order for order in orders if order.get('user_id') == user_id]