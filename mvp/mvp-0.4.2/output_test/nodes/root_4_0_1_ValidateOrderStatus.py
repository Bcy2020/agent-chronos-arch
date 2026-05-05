def ValidateOrderStatus(order: dict) -> dict:
    if order is None:
        raise ValueError('Order not found')
    if order['status'] not in ['pending', 'paid']:
        raise ValueError('Order not cancellable')
    return order