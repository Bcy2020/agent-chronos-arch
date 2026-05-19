def FormatResult(orders_list: list) -> dict:
    return {
        'success': True,
        'message': 'Orders listed successfully',
        'data': orders_list
    }