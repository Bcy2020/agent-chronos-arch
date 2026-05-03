def ReadOrder(order_id: int) -> dict:
    global orders
    for order in orders:
        if order['order_id'] == order_id:
            return order
    return None