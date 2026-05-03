def CompleteOrder(order_id: int) -> Tuple[bool, str]:
    order = GetOrder(order_id)
    if not CheckOrderStatus(order):
        return False, "Order does not exist or status is not shipped"
    if UpdateOrderStatus(order_id):
        return True, "Order completed successfully"
    else:
        return False, "Failed to update order status"