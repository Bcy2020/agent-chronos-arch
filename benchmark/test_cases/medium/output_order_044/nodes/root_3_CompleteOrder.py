def CompleteOrder(order_data: dict) -> dict:
    order = GetOrder(order_data)
    if order is None:
        return {'success': False, 'message': 'Order not found', 'data': None}
    is_shipped = CheckOrderStatus(order)
    if not is_shipped:
        return {'success': False, 'message': 'Order status is not shipped', 'data': None}
    result = UpdateOrderStatus(order_data)
    return {'success': True, 'message': 'Order completed successfully', 'data': result}