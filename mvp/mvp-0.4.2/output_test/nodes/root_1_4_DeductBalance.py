def DeductBalance(user_id: int, total_price: float) -> bool:
    try:
        user = update_user(user_id, {'balance': -total_price})
        return True
    except Exception:
        return False