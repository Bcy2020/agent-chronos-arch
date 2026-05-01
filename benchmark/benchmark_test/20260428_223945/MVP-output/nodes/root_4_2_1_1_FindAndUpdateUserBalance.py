def FindAndUpdateUserBalance(order: dict, should_refund: bool) -> bool:
    if not CheckRefundFlag(should_refund):
        return False
    user = FindUserById(order['user_id'])
    if user is None:
        return False
    return UpdateUserBalance(user, order['total'])