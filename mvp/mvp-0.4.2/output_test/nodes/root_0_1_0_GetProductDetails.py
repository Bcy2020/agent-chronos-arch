def GetProductDetails(product_id: int, quantity: int) -> Tuple[dict, bool]:
    product = get_product(product_id)
    if product is None:
        return None, False
    stock_ok = product['stock'] >= quantity
    return {'price': product['price'], 'stock': product['stock']}, stock_ok