def ListProducts(order_data: dict) -> dict:
    low_stock = ExtractLowStockFlag(order_data)
    products_list = ListProductsFromDB(low_stock)
    result = FormatResult(products_list)
    return result