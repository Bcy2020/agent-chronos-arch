def CompleteOrder(order_id: int) -> Tuple[bool, str, dict]:
    order = GetOrder(order_id)
    is_valid, message = ValidateOrderStatus(order)
    if not is_valid:
        return (False, message, {})
    success, data = UpdateOrderStatus(order_id, is_valid)
    if success:
        return (True, 'Order completed successfully', {})
    else:
        return (False, 'Failed to update order status', {})