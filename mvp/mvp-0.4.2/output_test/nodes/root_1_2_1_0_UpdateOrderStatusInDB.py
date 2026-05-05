def UpdateOrderStatusInDB(order: dict) -> None:
    update_order(order['order_id'], {'status': 'paid'})