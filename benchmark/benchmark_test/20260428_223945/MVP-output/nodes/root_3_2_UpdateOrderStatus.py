def UpdateOrderStatus(order_id: int, is_shipped: bool) -> bool:
    if not CheckShipped(is_shipped):
        return False
    return UpdateOrderStatusInStore(order_id)