def UpdateOrderStatusInStore(order: dict) -> bool:
    global orders
    for i, o in enumerate(orders):
        if o.get('id') == order.get('id'):
            orders[i]['status'] = 'cancelled'
            return True
    return False