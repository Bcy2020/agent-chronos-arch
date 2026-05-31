def ProcessOrder(input: Any) -> Any:
    parsed_command, parsed_order_data = ParseCommand(input)
    if parsed_command == 'place':
        result = PlaceOrder(parsed_order_data)
    elif parsed_command == 'cancel':
        result = CancelOrder(parsed_order_data)
    elif parsed_command == 'track':
        result = TrackOrder(parsed_order_data)
    else:
        result = {'success': False, 'message': 'Unknown command'}
    return result