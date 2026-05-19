def ComputeTotalSpent(orders: list) -> float:
    total = 0.0
    for order in orders:
        total += order.get('total_price', 0.0)
    return total