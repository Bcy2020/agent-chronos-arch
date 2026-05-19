def UpdateOrderStatus(order: dict) -> dict:
    order_id = order['order_id']
    result = update_order(order_id, {'status': 'cancelled'})
    return result