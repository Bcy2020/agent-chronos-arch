def RefundBalance(order: dict) -> bool:
    if CheckOrderStatus(order):
        user = GetUser(order['user_id'])
        return UpdateUserBalance(user, order['total'])
    return True