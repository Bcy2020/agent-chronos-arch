def handle_get_user_orders(order_data: dict) -> dict:
    user_id = ExtractUserId(order_data)
    orders = []  # placeholder, actual orders list is read by FilterOrdersByUser
    user_orders = FilterOrdersByUser(user_id, orders)
    total_spent = CalculateTotalSpent(user_orders)
    status_counts = CountOrdersPerStatus(user_orders)
    result = BuildSummary(user_orders, total_spent, status_counts)
    return result