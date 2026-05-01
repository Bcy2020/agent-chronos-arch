def SearchOrderInStore(order_id: int) -> Tuple[dict, Optional[str]]:
    # Access the global orders list
    global orders
    # Iterate through orders to find matching order_id
    for order in orders:
        if order.get('order_id') == order_id:
            return order, None
    # If not found, return None and error message
    return None, 'Order not found'