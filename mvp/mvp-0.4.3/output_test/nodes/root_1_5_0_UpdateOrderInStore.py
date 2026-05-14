def UpdateOrderInStore(order: dict) -> dict:
    if 'order_id' not in order:
        raise ValueError("order must contain 'order_id' key")
    updated_order = update_order(order['order_id'], {'status': 'paid'})
    return updated_order