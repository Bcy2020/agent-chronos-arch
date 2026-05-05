def ValidateOrderStatus(order: Optional[dict]) -> dict:
    if order is None:
        raise ValueError('Order not found')
    if order['status'] != 'pending':
        raise ValueError('Order status is not pending')
    return order