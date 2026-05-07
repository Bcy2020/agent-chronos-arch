def UpdateOrderStatus(order_id: int) -> dict:
    updates = {'status': 'shipped'}
    updated_order = update_order(order_id, updates)
    return updated_order