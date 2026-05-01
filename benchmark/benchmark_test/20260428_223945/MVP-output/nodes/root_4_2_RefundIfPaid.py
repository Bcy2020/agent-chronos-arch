def RefundIfPaid(order: dict) -> bool:
    is_paid = CheckOrderStatus(order)
    return RefundBalance(order, is_paid)