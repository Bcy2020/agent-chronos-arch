
def ProcessOrder(command: str, order_data: dict) -> dict:
    parsed_command, parsed_payload = ParseCommand(command, order_data)
    if parsed_command == "place":
        result = PlaceOrder(order_data)  # WRONG: should be parsed_payload
    return result
