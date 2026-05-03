def RefundBalance(order: dict, status: str) -> bool:
    if status == 'paid':
        user_id = order.get('user_id')
        total_price = order.get('total_price')
        if user_id is None or total_price is None:
            return False
        for user in users:
            if user['id'] == user_id:
                user['balance'] += total_price
                return True
    return False