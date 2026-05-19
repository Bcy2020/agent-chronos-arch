def ExtractFilters(order_data: dict) -> Tuple[Optional[int], Optional[str]]:
    user_filter = order_data.get('user_filter', None)
    status_filter = order_data.get('status_filter', None)
    return user_filter, status_filter