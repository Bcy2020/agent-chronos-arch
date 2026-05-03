def FilterOrdersByStatus(orders: list, status_filter: str) -> list:
    if status_filter is None:
        return orders
    return [order for order in orders if order.get('status') == status_filter]