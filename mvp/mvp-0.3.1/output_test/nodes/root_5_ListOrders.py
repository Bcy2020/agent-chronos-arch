def ListOrders(user_filter: int, status_filter: str) -> list:
    orders = RetrieveOrders()
    orders = FilterOrdersByUser(orders, user_filter)
    orders = FilterOrdersByStatus(orders, status_filter)
    return FormatOrderDetails(orders)