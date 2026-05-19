def GetOrder(order_data: dict) -> dict:
    order_id = order_data.get('order_id')
    if order_id is None:
        return None
    return get_order(order_id)