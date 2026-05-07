def CheckOrderPaid(order: Optional[dict]) -> bool:
    if order is None:
        return False
    return order.get('status') == 'paid'