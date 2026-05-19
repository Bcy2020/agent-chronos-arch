def ShipOrder(order_data: dict) -> dict:
    order = GetOrder(order_data)
    if order is None:
        return {'success': False, 'message': 'Order not found', 'data': None}
    if not ValidateOrderStatus(order):
        return {'success': False, 'message': 'Order status is not paid', 'data': None}
    updated_order = UpdateOrderStatus(order)
    return {'success': True, 'message': 'Order shipped successfully', 'data': updated_order}