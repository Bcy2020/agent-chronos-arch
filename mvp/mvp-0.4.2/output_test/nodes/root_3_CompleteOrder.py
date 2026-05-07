def CompleteOrder(order_data: dict) -> dict:
    order_id = order_data.get('order_id')
    if order_id is None:
        return {'error': 'Missing order_id'}
    order = GetOrder(order_id)
    is_valid = CheckOrderShipped(order)
    result = UpdateOrderStatus(order_id, is_valid)
    return result