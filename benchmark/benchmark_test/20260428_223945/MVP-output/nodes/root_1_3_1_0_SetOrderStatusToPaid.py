def SetOrderStatusToPaid(order: dict) -> dict:
    order['status'] = 'paid'
    return order