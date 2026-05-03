def CheckExistenceAndStatus(order: dict) -> Tuple[bool, bool]:
    if order is None:
        return (False, False)
    return (True, order.get('status') == 'paid')