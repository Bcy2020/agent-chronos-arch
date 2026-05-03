def CancelOrder(order_id: int) -> Tuple[bool, str]:
    try:
        order, status = ValidateOrder(order_id)
        RestoreStock(order)
        refunded = RefundBalance(order, status)
        UpdateOrderStatus(order)
        if refunded:
            return True, "Order cancelled and refunded."
        else:
            return True, "Order cancelled."
    except Exception as e:
        return False, str(e)