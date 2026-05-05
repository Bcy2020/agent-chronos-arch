def DeductBalanceAndUpdateOrder(user: dict, order: dict) -> float:
    new_balance = DeductBalance(user, order)
    UpdateOrderStatus(order)
    return new_balance