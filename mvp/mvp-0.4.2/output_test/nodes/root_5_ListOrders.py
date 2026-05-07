def ListOrders(order_data: dict) -> dict:
    status_filter, user_filter = ExtractFilters(order_data)
    orders_list = ListOrdersFromStore(status_filter, user_filter)
    return FormatSuccessResponse(orders_list)