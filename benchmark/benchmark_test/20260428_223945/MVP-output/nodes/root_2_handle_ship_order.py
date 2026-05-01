def handle_ship_order(order_data: dict) -> dict:
    order_id = order_data.get('order_id')
    if order_id is None:
        return {'success': False, 'message': 'Missing order_id', 'data': None}
    if not ValidateOrderExists(order_id):
        return {'success': False, 'message': 'Order not found', 'data': None}
    if not CheckOrderStatus(order_id):
        return {'success': False, 'message': 'Order status is not paid', 'data': None}
    if UpdateOrderStatus(order_id):
        return {'success': True, 'message': 'Order shipped successfully', 'data': None}
    else:
        return {'success': False, 'message': 'Failed to update order status', 'data': None}