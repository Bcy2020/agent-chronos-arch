def ValidateOrderStatus(order: Optional[dict]) -> Tuple[bool, str]:
    if order is None:
        return (False, 'Order not found')
    if order.get('status') != 'paid':
        return (False, 'Order status is not paid')
    return (True, '')