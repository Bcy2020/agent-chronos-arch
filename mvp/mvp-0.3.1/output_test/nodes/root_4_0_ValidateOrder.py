def ValidateOrder(order_id: int) -> Tuple[dict, str]:
    # Access the global orders list
    global orders
    # Search for the order by order_id
    for order in orders:
        if order['order_id'] == order_id:
            status = order.get('status', '')
            if status in ['pending', 'paid']:
                return order, status
            else:
                raise Exception(f"Order {order_id} has invalid status: {status}")
    raise Exception(f"Order {order_id} not found")