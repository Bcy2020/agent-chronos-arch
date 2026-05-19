def CreateOrderRecord(user_id: int, items: list, total_price: float) -> int:
    order = create_order({'user_id': user_id, 'items': items, 'total_price': total_price, 'status': 'pending'})
    return order['order_id']