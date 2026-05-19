def ListOrdersFromStore(user_filter: Optional[int], status_filter: Optional[str]) -> list:
    return list_orders(user_id=user_filter, status=status_filter)