def ValidateOrderStatus(order: dict) -> bool:
    if order['status'] in ['pending', 'paid']:
        return True
    else:
        raise ValueError("Order status must be 'pending' or 'paid'.")