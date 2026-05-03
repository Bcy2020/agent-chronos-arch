def ListProducts(low_stock: bool) -> list:
    all_products = GetAllProducts()
    return FilterLowStockProducts(all_products, low_stock)