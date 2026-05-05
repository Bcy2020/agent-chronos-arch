def CountOrdersByStatus(orders: list) -> dict:
    status_counts = {}
    for order in orders:
        status = order.get('status')
        if status:
            status_counts[status] = status_counts.get(status, 0) + 1
    return status_counts