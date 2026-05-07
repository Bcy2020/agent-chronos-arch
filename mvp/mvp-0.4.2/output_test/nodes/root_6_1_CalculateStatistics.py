def CalculateStatistics(orders: list) -> Tuple[float, dict]:
    total_spent = 0.0
    status_counts = {}
    for order in orders:
        status = order.get('status')
        total_price = order.get('total_price', 0.0)
        if status in ['paid', 'shipped', 'completed']:
            total_spent += total_price
        if status:
            status_counts[status] = status_counts.get(status, 0) + 1
    return total_spent, status_counts