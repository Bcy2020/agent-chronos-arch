def ListOrdersFromStore(user_filter: Optional[str], status_filter: Optional[str]) -> list:
    # Convert user_filter to int if provided, else None
    user_id = int(user_filter) if user_filter is not None else None
    # Call list_orders with the filters
    orders = list_orders(user_id=user_id, status=status_filter)
    return orders