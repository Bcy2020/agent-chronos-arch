def SearchOrders(order_id: int) -> dict:
    for order in orders:
        if order['order_id'] == order_id:
            return order
    return None