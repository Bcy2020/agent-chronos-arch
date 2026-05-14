def GetOrder(order_data: dict) -> dict:
    order_id = ExtractOrderId(order_data)
    order = RetrieveOrder(order_id)
    if order is None:
        raise ValueError(f"Order with id {order_id} not found")
    return order