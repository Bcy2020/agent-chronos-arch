def BuildSummary(user_orders: list, total_spent: float, status_counts: dict) -> dict:
    return {
        'success': True,
        'message': 'User orders retrieved',
        'data': {
            'orders': user_orders,
            'total_spent': total_spent,
            'status_counts': status_counts
        }
    }