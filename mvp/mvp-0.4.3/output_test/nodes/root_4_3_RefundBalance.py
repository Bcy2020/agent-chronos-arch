def RefundBalance(order: dict) -> bool:
    if order.get('status') == 'paid':
        user = get_user(order['user_id'])
        if user is None:
            return False
        new_balance = user['balance'] + order['total_price']
        update_user(order['user_id'], {'balance': new_balance})
        return True
    return False