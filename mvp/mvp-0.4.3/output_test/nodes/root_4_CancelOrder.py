def CancelOrder(order_data: dict) -> dict:
    try:
        order = GetOrder(order_data)
        if order is None:
            return {"success": False, "error": "Order not found"}
        ValidateOrderStatus(order)
        RestoreStock(order)
        RefundBalance(order)
        UpdateOrderStatus(order)
        return {"success": True, "message": "Order cancelled successfully"}
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}