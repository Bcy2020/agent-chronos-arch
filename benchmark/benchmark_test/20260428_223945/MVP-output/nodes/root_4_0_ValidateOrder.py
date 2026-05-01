def ValidateOrder(order_data: dict) -> Tuple[dict, Optional[str]]:
    order, error = GetOrderById(order_data)
    if error:
        return None, error
    return CheckOrderStatus(order)