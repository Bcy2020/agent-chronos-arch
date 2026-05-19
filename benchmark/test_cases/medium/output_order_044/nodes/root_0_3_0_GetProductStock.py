def GetProductStock(validated_items: list) -> dict:
    product_ids = ExtractProductIds(validated_items)
    product_stock_map = FetchProductStocks(product_ids)
    return product_stock_map