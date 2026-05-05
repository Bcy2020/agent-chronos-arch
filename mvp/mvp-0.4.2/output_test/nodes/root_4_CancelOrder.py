def CancelOrder(order_id: int) -> Tuple[bool, str, dict]:
    try:
        order = GetOrder(order_id)
    except Exception as e:
        return False, str(e), {}
    if not RestoreStock(order):
        return False, "Failed to restore stock", {}
    if not RefundBalance(order):
        return False, "Failed to refund balance", {}
    if not UpdateOrderStatus(order_id):
        return False, "Failed to update order status", {}
    return True, "Order cancelled successfully", {}