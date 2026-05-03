def GetUserOrdersList(user_id: int) -> list:
    # Access the global orders list
    global orders
    # Filter orders where order['user_id'] equals user_id
    return [order for order in orders if order['user_id'] == user_id]