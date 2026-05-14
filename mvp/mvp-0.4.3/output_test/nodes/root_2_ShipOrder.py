def ShipOrder(order_data: dict) -> dict:
    order = GetOrder(order_data)
    validation = ValidateOrderStatus(order)
    if 'error' in validation:
        return validation
    result = UpdateOrderStatus(order_data)
    return result