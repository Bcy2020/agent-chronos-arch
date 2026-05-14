def UpdateOrderStatus(order: dict, is_valid: bool) -> dict:
    if is_valid:
        update_order(order['order_id'], {'status': 'completed'})
        return {'success': True}
    else:
        return {'error': 'Order not shipped'}