def UpdateOrderStatus(order: dict) -> dict:
    updated_order = update_order(order['order_id'], {'status': 'paid'})
    return updated_order