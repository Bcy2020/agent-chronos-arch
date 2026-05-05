def ValidateOrderStatus(order: Optional[dict]) -> Tuple[bool, str]:
    if order is None:
        return (False, 'Order not found')
    if order.get('status') != 'shipped':
        return (False, 'Order status is not shipped')
    return (True, '')