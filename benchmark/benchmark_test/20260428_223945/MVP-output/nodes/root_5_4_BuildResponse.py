def BuildResponse(formatted_orders: list) -> dict:
    return {
        'success': True,
        'message': 'Orders retrieved successfully',
        'data': formatted_orders
    }