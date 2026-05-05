def UpdateOrderToCancelled(order_id: int) -> bool:
    try:
        update_order(order_id, {'status': 'cancelled'})
        return True
    except Exception:
        return False