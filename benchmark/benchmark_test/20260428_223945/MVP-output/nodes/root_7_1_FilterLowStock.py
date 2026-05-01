def FilterLowStock(products: list, order_data: dict) -> list:
    is_low_stock = CheckLowStockFlag(order_data)
    filtered_products = FilterProductsByStock(products, is_low_stock)
    return filtered_products