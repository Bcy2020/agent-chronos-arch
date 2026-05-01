def CheckOrderStatus(order_id: int, exists: bool) -> bool:
    if not exists:
        return False
    status = ReadOrderStatus(order_id)
    return CheckIfShipped(status)