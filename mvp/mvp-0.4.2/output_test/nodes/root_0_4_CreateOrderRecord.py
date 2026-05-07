def CreateOrderRecord(order_data: dict, total_price: float) -> dict:
    order = {
        'user_id': order_data['user_id'],
        'items': order_data['items'],
        'total_price': total_price,
        'status': 'pending'
    }
    created_order = create_order(order)
    return created_order