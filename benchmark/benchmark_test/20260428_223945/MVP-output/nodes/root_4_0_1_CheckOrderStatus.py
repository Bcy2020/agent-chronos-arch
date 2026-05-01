def CheckOrderStatus(order: dict) -> Tuple[dict, Optional[str]]:
    status = ExtractStatus(order)
    return ValidateStatus(status, order)