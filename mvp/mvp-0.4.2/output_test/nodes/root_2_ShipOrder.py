def ShipOrder(order_id: int) -> Tuple[bool, str, dict]:
    order = GetOrder(order_id)
    valid, message = ValidateOrderStatus(order)
    if not valid:
        return False, message, {}
    UpdateOrderStatus(order_id)
    return True, '', {}