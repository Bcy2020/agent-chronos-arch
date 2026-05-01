def CheckOrderStatus(order: dict) -> Tuple[bool, dict]:
    if order is None:
        return (False, None)
    if order.get('status') == 'pending':
        return (True, order)
    return (False, None)