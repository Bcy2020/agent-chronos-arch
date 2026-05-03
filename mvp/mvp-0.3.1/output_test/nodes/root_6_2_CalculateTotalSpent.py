def CalculateTotalSpent(orders_list: list) -> float:
    total = 0.0
    eligible_statuses = {'paid', 'shipped', 'completed'}
    for order in orders_list:
        if order.get('status') in eligible_statuses:
            total += order.get('total_price', 0.0)
    return total