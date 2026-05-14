def DeductSingleItemStock(product_id: int, quantity: int) -> bool:
    product = get_product(product_id)
    if product is None:
        return False
    new_stock = product['stock'] - quantity
    if new_stock < 0:
        return False
    update_product(product_id, {'stock': new_stock})
    return True