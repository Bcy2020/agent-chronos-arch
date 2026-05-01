def WriteUpdatedOrderToStore(updated_order: dict) -> bool:
    global orders
    for i, order in enumerate(orders):
        if order['id'] == updated_order['id']:
            orders[i] = updated_order
            return True
    return False