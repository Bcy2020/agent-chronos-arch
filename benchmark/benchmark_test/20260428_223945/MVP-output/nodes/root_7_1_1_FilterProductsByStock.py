def FilterProductsByStock(products: list, is_low_stock: bool) -> list:
    if is_low_stock:
        return [p for p in products if p.get('stock', 0) < 10]
    return products