def CheckOrderExistsAndPaid(order_id: int) -> Tuple[bool, bool]:
    order = ReadOrder(order_id)
    exists, is_paid = CheckExistenceAndStatus(order)
    return exists, is_paid