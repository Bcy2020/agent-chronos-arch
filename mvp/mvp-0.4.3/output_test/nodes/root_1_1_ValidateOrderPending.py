def ValidateOrderPending(order: dict) -> bool:
    return order.get('status') == 'pending'