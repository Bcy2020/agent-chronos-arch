def FilterLowStockProducts(products: list, low_stock: bool) -> list:
    if low_stock:
        return [p for p in products if p.get('stock', 0) < 10]
    return products