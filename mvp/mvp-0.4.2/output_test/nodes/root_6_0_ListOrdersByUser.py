def ListOrdersByUser(user_id: int) -> list:
    return list_orders(filters={'user_id': user_id})