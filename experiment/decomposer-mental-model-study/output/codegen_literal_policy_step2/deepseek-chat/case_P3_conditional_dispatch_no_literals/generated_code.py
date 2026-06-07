def ProcessOrder(input: dict) -> dict:
    command, payload = ParseInput(input)
    if command == 'place':
        result = PlaceOrder(payload)
    elif command == 'cancel':
        result = CancelOrder(payload)
    elif command == 'track':
        result = TrackOrder(payload)
    else:
        # Unreachable per constraints, but for completeness
        result = {}
    formatted = FormatResult(result)
    return formatted