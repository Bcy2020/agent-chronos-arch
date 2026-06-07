def ProcessPaidOrder(input: dict) -> dict:
    items, user_id, payment_info = ParseInput(input)
    return {"success": False, "message": "Payment failed"}
