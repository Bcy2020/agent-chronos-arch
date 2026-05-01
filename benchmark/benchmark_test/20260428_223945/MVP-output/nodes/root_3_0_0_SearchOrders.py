def SearchOrders(order_id: int) -> bool:
    global orders
    for order in orders:
        if order['id'] == order_id:
            return True
    return False