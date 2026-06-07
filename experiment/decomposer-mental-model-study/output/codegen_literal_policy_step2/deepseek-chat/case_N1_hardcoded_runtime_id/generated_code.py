def CreateOrder(input: dict) -> dict:
    command, payload = ParseInput(input)
    payment_result = ProcessPayment(payload)
    return {"success": True, "order_id": "ORDER-001"}
