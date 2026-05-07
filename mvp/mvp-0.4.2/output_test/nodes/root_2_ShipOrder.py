def ShipOrder(order_data: dict) -> dict:
    order_id = order_data.get('order_id')
    if order_id is None:
        return {'success': False, 'error': 'Missing order_id'}
    order = GetOrder(order_id)
    if not CheckOrderPaid(order):
        return {'success': False, 'error': 'Order not found or not paid'}
    result = UpdateOrderStatus(order_id)
    return {'success': True, 'data': result}