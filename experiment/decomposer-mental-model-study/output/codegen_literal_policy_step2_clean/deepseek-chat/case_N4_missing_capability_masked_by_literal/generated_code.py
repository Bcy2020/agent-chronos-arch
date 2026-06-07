def Checkout(cart: dict) -> dict:
    # BAD: no payment child available, uses literal fallback to mask missing capability
    parsed = ParseCheckout(cart)
    reserved = ReserveInventory(parsed)
    return {"success": False, "message": "Payment failed"}
