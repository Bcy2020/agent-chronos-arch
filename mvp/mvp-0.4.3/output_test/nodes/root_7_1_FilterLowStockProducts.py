def FilterLowStockProducts(products_list: list, order_data: dict) -> list:
    if order_data.get('low_stock'):
        return [p for p in products_list if p.get('stock', 0) < 10]
    return products_list