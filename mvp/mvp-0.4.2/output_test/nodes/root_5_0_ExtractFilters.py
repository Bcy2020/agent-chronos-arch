def ExtractFilters(order_data: dict) -> Tuple[str, str]:
    status_filter = order_data.get('status_filter', None)
    user_filter = order_data.get('user_filter', None)
    return status_filter, user_filter