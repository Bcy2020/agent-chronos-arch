def CreateOrder(user_id: int, items: list) -> Tuple[int, float]:
    if not ValidateUser(user_id):
        raise ValueError("User does not exist")
    if not CheckProductStock(items):
        raise ValueError("Insufficient stock")
    total_price = CalculateTotalPrice(items)
    DeductStock(items)
    order_id = CreateOrderRecord(user_id, items, total_price)
    return (order_id, total_price)