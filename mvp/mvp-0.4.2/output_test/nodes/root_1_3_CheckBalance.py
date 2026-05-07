def CheckBalance(user: Optional[dict], total_price: float) -> bool:
    if user is None:
        return False
    return user.get('balance', 0) >= total_price