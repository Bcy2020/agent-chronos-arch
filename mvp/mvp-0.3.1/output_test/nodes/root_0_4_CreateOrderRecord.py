def CreateOrderRecord(user_id: int, items: list, total_price: float) -> int:
    global orders
    # Generate new order ID (incrementing from existing orders)
    if not orders:
        new_id = 1
    else:
        new_id = max(order['order_id'] for order in orders) + 1
    # Create order record
    order = {
        'order_id': new_id,
        'user_id': user_id,
        'items': items,
        'total_price': total_price,
        'status': 'pending'
    }
    # Append to orders list
    orders.append(order)
    return new_id