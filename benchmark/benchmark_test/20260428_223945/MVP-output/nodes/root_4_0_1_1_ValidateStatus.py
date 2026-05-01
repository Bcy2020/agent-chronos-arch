def ValidateStatus(status: str, order: dict) -> Tuple[dict, Optional[str]]:
    if status in ['pending', 'paid']:
        return order, None
    else:
        return None, 'Invalid order status'