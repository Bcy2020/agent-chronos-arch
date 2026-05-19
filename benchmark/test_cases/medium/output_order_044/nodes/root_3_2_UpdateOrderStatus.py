def UpdateOrderStatus(order_data: dict) -> dict:
    order_id = order_data['order_id']
    return update_order(order_id, {'status': 'completed'})