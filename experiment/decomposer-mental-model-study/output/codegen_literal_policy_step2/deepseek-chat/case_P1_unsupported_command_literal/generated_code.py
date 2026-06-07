def ProcessOrder(input: dict) -> Tuple[bool, str, dict]:
    command, payload = ParseInput(input)
    if command == 'place':
        result = PlaceOrder(payload)
        return True, 'Order placed successfully', result
    elif command == 'cancel':
        result = CancelOrder(payload)
        return True, 'Order cancelled successfully', result
    elif command == 'track':
        result = TrackOrder(payload)
        return True, 'Order tracked successfully', result
    else:
        return False, 'Unsupported command', {}