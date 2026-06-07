def GetOrderStatus(order_id: str) -> str:
    status = FetchOrderStatus(order_id)
    return status