
def ProcessOrder(command: str, payload: dict) -> dict:
    result = RouteCommand(command, payload)
    return result
