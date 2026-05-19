def ValidateOrderStatus(order: dict) -> dict:
    if order['status'] in ['pending', 'paid']:
        return {'valid': True}
    else:
        return {'valid': False, 'error': 'Order status must be pending or paid'}