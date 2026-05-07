def UpdateOrderStatus(order_id: int) -> bool:
    try:
        result = update_order(order_id, {'status': 'paid'})
        return True
    except Exception:
        return False