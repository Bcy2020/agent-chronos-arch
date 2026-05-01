def FindOrderInList(orders_list: list, order_id: int) -> dict:
    for order in orders_list:
        if order.get('id') == order_id:
            return order
    return None