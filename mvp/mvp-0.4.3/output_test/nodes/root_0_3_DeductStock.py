def DeductStock(items: list, product_details: list) -> bool:
    for item in items:
        product_id = item['product_id']
        quantity = item['quantity']
        success = DeductSingleItemStock(product_id, quantity)
        if not success:
            return False
    return True