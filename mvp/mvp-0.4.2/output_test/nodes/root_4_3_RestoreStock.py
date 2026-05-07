def RestoreStock(items: list) -> Tuple[bool, str]:
    for item in items:
        success, error = RestoreSingleItemStock(item)
        if not success:
            return False, error
    return True, ""