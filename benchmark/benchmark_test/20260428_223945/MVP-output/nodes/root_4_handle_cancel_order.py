def handle_cancel_order(order_data: dict) -> dict:
    order, error = ValidateOrder(order_data)
    if error:
        return ComposeResult(order, error, False, False, False)
    stock_restored = RestoreStock(order)
    refunded = RefundIfPaid(order)
    status_updated = UpdateOrderStatus(order)
    return ComposeResult(order, None, stock_restored, refunded, status_updated)