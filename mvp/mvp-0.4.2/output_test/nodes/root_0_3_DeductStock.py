def DeductStock(items: list) -> Tuple[bool, Optional[str]]:
    for item in items:
        product_id = item['product_id']
        quantity = item['quantity']
        success, error = DeductSingleItemStock(product_id, quantity)
        if not success:
            return False, error
    return True, None