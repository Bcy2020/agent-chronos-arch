def GetUserOrders(order_data: dict) -> dict:
    user_id = order_data['user_id']
    orders = ListOrdersByUser(user_id)
    total_spent, status_counts = CalculateStatistics(orders)
    return {'success': True, 'data': {'orders': orders, 'total_spent': total_spent, 'status_counts': status_counts}}