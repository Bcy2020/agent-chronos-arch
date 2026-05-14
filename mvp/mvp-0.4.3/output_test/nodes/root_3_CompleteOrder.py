def CompleteOrder(order_data: dict) -> dict:
    order = GetOrder(order_data)
    is_valid = ValidateOrderStatus(order)
    result = UpdateOrderStatus(order, is_valid)
    return result