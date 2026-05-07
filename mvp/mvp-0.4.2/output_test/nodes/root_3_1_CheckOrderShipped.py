def CheckOrderShipped(order: Optional[dict]) -> bool:
    if order is None:
        return False
    return order.get('status') == 'shipped'