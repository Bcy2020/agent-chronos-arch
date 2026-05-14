def ValidateOrderStatus(order: dict) -> bool:
    if order is None:
        return False
    return order.get('status') == 'shipped'