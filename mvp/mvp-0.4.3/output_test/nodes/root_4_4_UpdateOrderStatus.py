def UpdateOrderStatus(order: dict) -> bool:
    try:
        result = update_order(order['order_id'], {'status': 'cancelled'})
        return result.get('status') == 'cancelled'
    except Exception:
        return False