def ProcessOrder(command: str, order_data: dict) -> dict:
    parsed_command, parsed_payload = ParseCommand(command, order_data)
    if parsed_command == 'place':
        result = PlaceOrder(parsed_payload)
    elif parsed_command == 'cancel':
        result = CancelOrder(parsed_payload)
    elif parsed_command == 'track':
        result = TrackOrder(parsed_payload)
    else:
        result = {'success': False, 'order_id': None, 'status': 'error', 'message': 'Invalid command'}
    order_result = FormatResult(result)
    return order_result