def UpdateOrderStatus(order_id: int, is_valid: bool) -> dict:
    if not is_valid:
        return {'error': 'Invalid order'}
    result = update_order(order_id, {'status': 'completed'})
    return {'success': True}