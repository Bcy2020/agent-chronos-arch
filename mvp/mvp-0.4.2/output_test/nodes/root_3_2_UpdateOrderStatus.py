def UpdateOrderStatus(order_id: int, is_valid: bool) -> Tuple[bool, dict]:
    if is_valid:
        update_order(order_id, {'status': 'completed'})
        return (True, {})
    else:
        return (False, {})