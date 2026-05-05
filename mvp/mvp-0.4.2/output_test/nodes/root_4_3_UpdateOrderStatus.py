def UpdateOrderStatus(order_id: int) -> bool:
    if not ValidateOrderExists(order_id):
        return False
    return UpdateOrderToCancelled(order_id)