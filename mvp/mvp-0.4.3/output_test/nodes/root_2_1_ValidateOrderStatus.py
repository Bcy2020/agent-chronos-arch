def ValidateOrderStatus(order: dict) -> dict:
    if order is None:
        return {'error': 'Order not found'}
    if order.get('status') != 'paid':
        return {'error': 'Order status is not paid'}
    return {'success': True}