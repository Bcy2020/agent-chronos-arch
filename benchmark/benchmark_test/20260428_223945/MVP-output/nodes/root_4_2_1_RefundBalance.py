def RefundBalance(order: dict, is_paid: bool) -> bool:
    should_refund = CheckPaymentStatus(is_paid)
    return FindAndUpdateUserBalance(order, should_refund)