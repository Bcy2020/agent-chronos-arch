def CheckStock(items: list) -> Tuple[bool, Optional[str]]:
    for item in items:
        product_id = item['product_id']
        quantity = item['quantity']
        stock_ok, error_message = CheckSingleItem(product_id, quantity)
        if not stock_ok:
            return (False, error_message)
    return (True, None)