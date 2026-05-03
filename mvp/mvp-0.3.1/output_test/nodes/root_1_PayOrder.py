def PayOrder(order_id: int) -> Tuple[bool, str]:
    order = GetOrder(order_id)
    if not ValidateOrderStatus(order):
        return False, "Order does not exist or is not pending"
    user_id = order['user_id']
    user = GetUser(user_id)
    if user is None:
        return False, "User not found"
    if not CheckBalance(user, order):
        return False, "Insufficient balance"
    if not DeductBalance(user_id, order['total_price']):
        return False, "Failed to deduct balance"
    if not UpdateOrderStatus(order_id):
        return False, "Failed to update order status"
    return True, "Payment successful"