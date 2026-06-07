def ProcessOrder(input: dict) -> dict:
    command, payload = ParseInput(input)
    if command == 'place':
        result = PlaceOrder(payload)
    elif command == 'cancel':
        result = CancelOrder(payload)
    elif command == 'track':
        result = TrackOrder(payload)
    else:
        return {'success': False, 'message': 'Unsupported command'}
    response = FormatResult(result)
    return response