def CheckOrderStatus(order: dict) -> bool:
    return order.get('status') == 'paid'