def GetUserOrders(order_data: dict) -> dict:
    user_id = order_data['user_filter']['user_id']
    orders_list = ListOrdersForUser(user_id)
    total_spent = CalculateTotalSpent(orders_list)
    status_counts = CountOrdersByStatus(orders_list)
    return {
        'success': True,
        'data': {
            'orders': orders_list,
            'total_spent': total_spent,
            'status_counts': status_counts
        }
    }