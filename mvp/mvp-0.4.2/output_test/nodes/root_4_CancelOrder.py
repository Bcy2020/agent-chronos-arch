def CancelOrder(order_data: dict) -> dict:
    order_id = order_data.get('order_id')
    if order_id is None:
        return {'success': False, 'error': 'Missing order_id'}
    order = GetOrder(order_id)
    valid, error = ValidateOrderStatus(order)
    if not valid:
        return {'success': False, 'error': error}
    items = GetOrderItems(order)
    success, error = RestoreStock(items)
    if not success:
        return {'success': False, 'error': error}
    is_paid = order['status'] == 'paid'
    success, error = RefundBalance(order, is_paid)
    if not success:
        return {'success': False, 'error': error}
    success, error = UpdateOrderStatus(order_id)
    if not success:
        return {'success': False, 'error': error}
    return {'success': True, 'message': 'Order cancelled successfully'}