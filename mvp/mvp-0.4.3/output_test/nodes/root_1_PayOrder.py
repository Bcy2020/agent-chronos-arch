def PayOrder(order_data: dict) -> dict:
    try:
        order = GetOrder(order_data)
        if not ValidateOrderPending(order):
            return {"success": False, "error": "Order status is not pending"}
        user = GetUser(order)
        if not CheckBalance(user, order):
            return {"success": False, "error": "Insufficient balance"}
        DeductBalance(user, order)
        UpdateOrderStatus(order)
        return {"success": True, "message": "Payment successful"}
    except Exception as e:
        return {"success": False, "error": str(e)}