def UpdateOrderStatus(order_id: int) -> bool:
    global orders
    for order in orders:
        if order['id'] == order_id:
            if order['status'] == 'paid':
                order['status'] = 'shipped'
                return True
            else:
                return False
    return False