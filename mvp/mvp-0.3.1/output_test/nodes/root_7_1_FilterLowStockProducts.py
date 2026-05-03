def FilterLowStockProducts(all_products: list, low_stock: bool) -> list:
    if low_stock:
        return [p for p in all_products if p.get('stock', 0) < 10]
    else:
        return all_products