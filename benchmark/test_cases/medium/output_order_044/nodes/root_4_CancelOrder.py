def CancelOrder(order_data: dict) -> dict:
    order = GetOrder(order_data)
    if order is None:
        return {'success': False, 'message': 'Order not found', 'data': None}
    validation = ValidateOrderStatus(order)
    if not validation['valid']:
        return {'success': False, 'message': validation['error'], 'data': None}
    restore_result = RestoreStock(order)
    if not restore_result.get('success', True):
        return {'success': False, 'message': 'Failed to restore stock', 'data': None}
    if order['status'] == 'paid':
        refund_result = RefundBalance(order)
        if not refund_result.get('success', True):
            return {'success': False, 'message': 'Failed to refund balance', 'data': None}
    update_result = UpdateOrderStatus(order)
    if not update_result.get('success', True):
        return {'success': False, 'message': 'Failed to update order status', 'data': None}
    return {'success': True, 'message': 'Order cancelled successfully', 'data': None}