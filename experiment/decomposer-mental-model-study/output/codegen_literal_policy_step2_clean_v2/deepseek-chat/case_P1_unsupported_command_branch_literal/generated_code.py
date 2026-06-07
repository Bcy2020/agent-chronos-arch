def ProcessOrder(input: dict) -> dict:
    command, payload = ParseInput(input)
    if command == 'place':
        handler_result = PlaceOrder(payload)
    elif command == 'cancel':
        handler_result = CancelOrder(payload)
    elif command == 'track':
        handler_result = TrackOrder(payload)
    else:
        return {'success': False, 'message': 'Unsupported command'}
    response = FormatResult(handler_result)
    return response