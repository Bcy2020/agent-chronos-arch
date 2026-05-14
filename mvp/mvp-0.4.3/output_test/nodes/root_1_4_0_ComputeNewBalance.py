def ComputeNewBalance(user: dict, order: dict) -> float:
    new_balance = user['balance'] - order['total_price']
    if new_balance < 0:
        raise ValueError('new_balance must be non-negative')
    return new_balance