def UpdateOrderStatus(order_id: int) -> bool:
    update_order(order_id, {'status': 'shipped'})
    return True