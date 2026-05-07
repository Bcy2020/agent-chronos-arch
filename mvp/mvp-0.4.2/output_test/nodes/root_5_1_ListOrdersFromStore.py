def ListOrdersFromStore(status_filter: str, user_filter: str) -> list:
    filters = {}
    if status_filter is not None:
        filters['status'] = status_filter
    if user_filter is not None:
        filters['user_id'] = user_filter
    return list_orders(filters)