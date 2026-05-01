def GetOrderById(order_data: dict) -> Tuple[dict, Optional[str]]:
    order_id = ExtractOrderId(order_data)
    order, error = SearchOrderInStore(order_id)
    return order, error