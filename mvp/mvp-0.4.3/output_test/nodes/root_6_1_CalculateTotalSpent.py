def CalculateTotalSpent(orders_list: list) -> float:
    total = 0.0
    for order in orders_list:
        if order.get('status') in ['paid', 'shipped', 'completed']:
            total += order.get('total', 0.0)
    return total