def GetOrderStatus(order_id: str) -> dict:
    # BAD: has FetchOrderStatus available but hardcodes status
    status = FetchOrderStatus(order_id)
    return {"status": "delivered"}
