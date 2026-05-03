def UpdateOrderStatusToShipped(order_id: int) -> Tuple[bool, str]:
    return UpdateOrderStatus(order_id)