def GetOrderItems(order: dict) -> list:
    return order.get('items', [])