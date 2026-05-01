def handle_pay_order(order_data: dict) -> dict:
    order_id = order_data.get('order_id')
    if order_id is None:
        return ComposeResult(False, 'Missing order_id')
    valid, order = ValidateOrder(order_id)
    if not valid:
        return ComposeResult(False, 'Order not found or not pending')
    user_id = order.get('user_id')
    total_amount = order.get('total_amount')
    if not CheckBalance(user_id, total_amount):
        return ComposeResult(False, 'Insufficient balance')
    if not DeductBalance(user_id, total_amount):
        return ComposeResult(False, 'Failed to deduct balance')
    if not UpdateOrderStatus(order_id):
        return ComposeResult(False, 'Failed to update order status')
    return ComposeResult(True, 'Payment successful')