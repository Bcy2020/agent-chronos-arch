def FormatOrderList(filtered_orders: list) -> list:
    formatted_orders = []
    for order in filtered_orders:
        formatted_order = {
            'items': order.get('items', []),
            'total_price': order.get('total_price', 0.0),
            'status': order.get('status', ''),
            'creation_time': order.get('creation_time', '')
        }
        formatted_orders.append(formatted_order)
    return formatted_orders