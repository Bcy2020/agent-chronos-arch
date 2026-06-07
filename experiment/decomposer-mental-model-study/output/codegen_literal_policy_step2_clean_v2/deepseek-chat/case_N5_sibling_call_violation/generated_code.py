def RouteOrder(input: dict) -> Tuple[bool, dict]:
    parsed = ParseInput(input)
    command = parsed['command']
    data = parsed['data']
    result = RouteCommand(command, data)
    return True, result