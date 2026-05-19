def ListOrders(order_data: dict) -> dict:
    user_filter, status_filter = ExtractFilters(order_data)
    orders_list = ListOrdersFromStore(user_filter, status_filter)
    result = FormatResult(orders_list)
    return result