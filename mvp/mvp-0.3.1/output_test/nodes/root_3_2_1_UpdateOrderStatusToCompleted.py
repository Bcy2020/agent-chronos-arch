def UpdateOrderStatusToCompleted(order: dict) -> bool:
    order['status'] = 'completed'
    return True