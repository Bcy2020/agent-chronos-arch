def FilterOrders(all_orders: list, status_filter: Optional[str], user_filter: Optional[str]) -> list:
    filtered = all_orders
    if status_filter is not None:
        filtered = [order for order in filtered if order.get('status') == status_filter]
    if user_filter is not None:
        filtered = [order for order in filtered if order.get('user') == user_filter]
    return filtered