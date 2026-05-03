def UpdateOrderStatus(order: dict) -> bool:
    global orders
    for o in orders:
        if o['id'] == order['id']:
            o['status'] = 'cancelled'
            return True
    return False