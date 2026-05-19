def UpdateOrderStatus(order: dict) -> dict:
    updated_order = update_order(order['order_id'], {'status': 'shipped'})
    return updated_order