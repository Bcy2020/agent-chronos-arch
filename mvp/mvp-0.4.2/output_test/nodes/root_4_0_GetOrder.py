def GetOrder(order_id: int) -> dict:
    order = FetchOrder(order_id)
    return ValidateOrderStatus(order)