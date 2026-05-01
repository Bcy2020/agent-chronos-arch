def ValidateOrderExists(order_id: int) -> bool:
    # Access the global orders list
    global orders
    # Check if order_id is a valid integer
    if not isinstance(order_id, int):
        return False
    # Search for the order with matching order_id
    for order in orders:
        if order.get('order_id') == order_id:
            return True
    return False