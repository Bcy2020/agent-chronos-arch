def UpdateOrderStatus(order_id: int) -> bool:
    order = FindOrderById(order_id)
    if order is None:
        return False
    return UpdateOrderStatusInStore(order)