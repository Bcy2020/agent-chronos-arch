def ListOrdersFromStore(user_filter: int, status_filter: str) -> list:
    return list_orders(user_id=user_filter, status=status_filter)