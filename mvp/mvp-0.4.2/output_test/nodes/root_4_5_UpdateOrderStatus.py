def UpdateOrderStatus(order_id: int) -> Tuple[bool, str]:
    try:
        result = update_order(order_id, {'status': 'cancelled'})
        if result.get('status') == 'cancelled':
            return True, ''
        else:
            return False, 'Failed to update order status'
    except Exception as e:
        return False, str(e)