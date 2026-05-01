def ExtractFilters(order_data: dict) -> Tuple[Optional[str], Optional[str]]:
    status_filter = order_data.get('status_filter', None)
    user_filter = order_data.get('user_filter', None)
    return status_filter, user_filter