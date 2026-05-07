def CheckOrderPending(order: Optional[dict]) -> bool:
    if order is None or order.get('status') != 'pending':
        return False
    return True