def ValidateOrderStatus(order: dict) -> bool:
    if order is None or order.get('status') != 'pending':
        return False
    return True