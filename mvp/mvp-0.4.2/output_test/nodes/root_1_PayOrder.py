def PayOrder(order_data: dict) -> dict:
    order_id = order_data.get('order_id')
    if order_id is None:
        return {'success': False, 'error': 'Missing order_id'}
    order = GetOrder(order_id)
    if not CheckOrderPending(order):
        return {'success': False, 'error': 'Order not found or not pending'}
    user_id = order['user_id']
    total_price = order['total_price']
    user = GetUser(user_id)
    if not CheckBalance(user, total_price):
        return {'success': False, 'error': 'Insufficient balance or user not found'}
    if not DeductBalance(user_id, total_price):
        return {'success': False, 'error': 'Failed to deduct balance'}
    if not UpdateOrderStatus(order_id):
        return {'success': False, 'error': 'Failed to update order status'}
    return {'success': True}