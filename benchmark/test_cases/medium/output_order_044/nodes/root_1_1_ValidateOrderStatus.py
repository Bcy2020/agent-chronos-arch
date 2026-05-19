def ValidateOrderStatus(order: dict) -> bool:
    return order.get('status') == 'pending'