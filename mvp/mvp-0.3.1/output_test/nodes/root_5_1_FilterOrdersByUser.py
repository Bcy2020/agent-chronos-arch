def FilterOrdersByUser(orders: list, user_filter: int) -> list:
    if user_filter is not None:
        return [order for order in orders if order['user_id'] == user_filter]
    return orders