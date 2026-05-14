def ValidateStock(items: list) -> Tuple[bool, list]:
    product_details = GetProductDetails(items)
    stock_valid, valid_product_details = CheckStockSufficiency(items, product_details)
    return stock_valid, valid_product_details