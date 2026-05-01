def CheckBalance(user_id: int, total_amount: float) -> bool:
    balance = FetchUserBalance(user_id)
    return CompareBalance(balance, total_amount)