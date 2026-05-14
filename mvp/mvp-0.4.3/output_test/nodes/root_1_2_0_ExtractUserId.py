def ExtractUserId(order: dict) -> int:
    if 'user_id' not in order:
        raise KeyError("order must have 'user_id' key")
    return order['user_id']