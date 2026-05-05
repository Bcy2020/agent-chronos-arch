def CreateOrder(user_id: int, items: list) -> Tuple[bool, str, dict]:
    if not ValidateUser(user_id):
        return False, "User does not exist", {}
    stock_ok, product_details = CheckStock(items)
    if not stock_ok:
        return False, "Insufficient stock for one or more items", {}
    total_price = CalculateTotalPrice(product_details)
    if not DeductStock(items, product_details):
        return False, "Failed to deduct stock", {}
    order_id = CreateOrderRecord(user_id, items, total_price)
    return True, "Order created successfully", {"order_id": order_id, "total_price": total_price}