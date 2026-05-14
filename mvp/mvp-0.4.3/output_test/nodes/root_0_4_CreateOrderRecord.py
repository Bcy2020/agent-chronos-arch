def CreateOrderRecord(user_id: int, items: list, total_price: float) -> int:
    order = {
        'user_id': user_id,
        'items': items,
        'total_price': total_price,
        'status': 'pending'
    }
    created_order = create_order(order)
    return created_order['order_id']