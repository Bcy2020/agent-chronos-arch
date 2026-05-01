def UpdateOrderStatusInStore(order_id: int) -> bool:
    global orders
    for order in orders:
        if order['id'] == order_id:
            order['status'] = 'completed'
            return True
    return False