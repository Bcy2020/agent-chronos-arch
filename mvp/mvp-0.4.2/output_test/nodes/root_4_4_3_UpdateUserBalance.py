def UpdateUserBalance(user_id: int, new_balance: float) -> Tuple[bool, str]:
    try:
        result = update_user(user_id, {'balance': new_balance})
        if result.get('success', False):
            return (True, '')
        else:
            return (False, result.get('error', 'Unknown error'))
    except Exception as e:
        return (False, str(e))