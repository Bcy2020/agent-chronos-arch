def handle_list_orders(order_data: dict) -> dict:
    status_filter, user_filter = ExtractFilters(order_data)
    all_orders = ReadOrders()
    filtered_orders = FilterOrders(all_orders, status_filter, user_filter)
    formatted_orders = FormatOrderList(filtered_orders)
    result = BuildResponse(formatted_orders)
    return result