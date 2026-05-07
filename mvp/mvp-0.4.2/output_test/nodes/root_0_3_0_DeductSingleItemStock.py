def DeductSingleItemStock(product_id: int, quantity: int) -> Tuple[bool, Optional[str]]:
    product = get_product(product_id)
    if product is None:
        return False, "Product not found"
    new_stock = product['stock'] - quantity
    if new_stock < 0:
        return False, "Insufficient stock"
    try:
        update_product(product_id, {'stock': new_stock})
        return True, None
    except Exception as e:
        return False, str(e)