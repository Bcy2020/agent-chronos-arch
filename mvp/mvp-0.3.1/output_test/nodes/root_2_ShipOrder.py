def ShipOrder(order_id: int) -> Tuple[bool, str]:
    exists, is_paid = CheckOrderExistsAndPaid(order_id)
    if not exists:
        return False, "Order not found"
    if not is_paid:
        return False, "Order status is not paid"
    success, message = UpdateOrderStatusToShipped(order_id)
    return success, message