def FormatSuccessResponse(orders_list: list) -> dict:
    return {'success': True, 'data': {'orders': orders_list}}