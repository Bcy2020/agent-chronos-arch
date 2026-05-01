def FindOrderById(order_id: int) -> dict:
    orders_list = ReadOrdersList()
    return FindOrderInList(orders_list, order_id)