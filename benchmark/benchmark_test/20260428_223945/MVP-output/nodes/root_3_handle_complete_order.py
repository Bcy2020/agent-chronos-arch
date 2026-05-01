def handle_complete_order(order_data: dict) -> dict:
    order_id = order_data.get('order_id')
    if order_id is None:
        return {'success': False, 'message': 'Missing order_id', 'data': None}
    exists = ValidateOrderExists(order_id)
    if not exists:
        return {'success': False, 'message': 'Order not found', 'data': None}
    is_shipped = CheckOrderStatus(order_id, exists)
    if not is_shipped:
        return {'success': False, 'message': 'Order status is not shipped', 'data': None}
    success = UpdateOrderStatus(order_id, is_shipped)
    if success:
        return {'success': True, 'message': 'Order completed successfully', 'data': None}
    else:
        return {'success': False, 'message': 'Failed to update order status', 'data': None}