def FindOrderById(order_id: int) -> Optional[dict]:
    for order in orders:
        if order.get('id') == order_id:
            return order
    return None