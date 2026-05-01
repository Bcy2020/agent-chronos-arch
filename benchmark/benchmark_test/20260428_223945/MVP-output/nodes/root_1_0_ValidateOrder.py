def ValidateOrder(order_id: int) -> Tuple[bool, dict]:
    order = FetchOrder(order_id)
    return CheckOrderStatus(order)