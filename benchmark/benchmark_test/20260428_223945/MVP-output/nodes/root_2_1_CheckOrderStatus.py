def CheckOrderStatus(order_id: int) -> bool:
    # Access the global orders list
    global orders
    # Iterate through orders to find the one with matching order_id
    for order in orders:
        if order['id'] == order_id:
            # Check if status is 'paid'
            return order.get('status') == 'paid'
    # If order not found, return False (though precondition says order exists)
    return False