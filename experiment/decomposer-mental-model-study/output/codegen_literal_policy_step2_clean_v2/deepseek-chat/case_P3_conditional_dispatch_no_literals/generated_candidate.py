def ProcessAction(input: dict) -> dict:
    parsed = ParseAction(input)
    action = parsed['action']
    data = parsed['data']
    if action == 'create':
        handler_result = CreateHandler(data)
    elif action == 'update':
        handler_result = UpdateHandler(data)
    elif action == 'delete':
        handler_result = DeleteHandler(data)
    else:
        return {'success': False, 'result': 'Unsupported action'}
    response = FormatAction(handler_result)
    return response