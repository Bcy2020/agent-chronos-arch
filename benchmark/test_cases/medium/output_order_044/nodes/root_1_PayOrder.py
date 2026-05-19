def PayOrder(order_data: dict) -> dict:
    order = GetOrder(order_data)
    if order is None:
        return {'success': False, 'message': 'Order not found', 'data': None}
    if not ValidateOrderStatus(order):
        return {'success': False, 'message': 'Order status is not pending', 'data': None}
    user = GetUser(order)
    if user is None:
        return {'success': False, 'message': 'User not found', 'data': None}
    if not CheckBalance(user, order):
        return {'success': False, 'message': 'Insufficient balance', 'data': None}
    updated_user = DeductBalance(user, order)
    updated_order = UpdateOrderStatus(order)
    return {'success': True, 'message': 'Payment successful', 'data': {'order': updated_order, 'user': updated_user}}