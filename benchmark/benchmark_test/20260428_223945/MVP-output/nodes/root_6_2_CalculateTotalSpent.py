def CalculateTotalSpent(user_orders: list) -> float:
    total = 0.0
    for order in user_orders:
        if order.get('status') == 'completed':
            total += order.get('total_price', 0.0)
    return total