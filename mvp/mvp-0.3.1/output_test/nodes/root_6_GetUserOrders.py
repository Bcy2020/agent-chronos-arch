def GetUserOrders(user_id: int) -> dict:
    if not ValidateUser(user_id):
        raise ValueError(f"User {user_id} does not exist")
    orders_list = GetUserOrdersList(user_id)
    total_spent = CalculateTotalSpent(orders_list)
    status_counts = CountOrdersByStatus(orders_list)
    return {
        "orders": orders_list,
        "total_spent": total_spent,
        "status_counts": status_counts
    }