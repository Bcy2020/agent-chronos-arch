def GetUserOrders(user_id: int) -> Tuple[bool, str, dict]:
    orders = ListUserOrders(user_id)
    total_spent = CalculateTotalSpent(orders)
    status_counts = CountOrdersByStatus(orders)
    data = {
        "orders": orders,
        "total_spent": total_spent,
        "status_counts": status_counts
    }
    return True, "Orders retrieved successfully", data