def FormatOrderDetails(orders: list) -> list:
    formatted_orders = []
    for order in orders:
        formatted_order = {
            'items': order.get('items', []),
            'total_price': order.get('total_price', 0.0),
            'status': order.get('status', ''),
            'created_at': order.get('created_at', ''),
            'updated_at': order.get('updated_at', '')
        }
        formatted_orders.append(formatted_order)
    return formatted_orders