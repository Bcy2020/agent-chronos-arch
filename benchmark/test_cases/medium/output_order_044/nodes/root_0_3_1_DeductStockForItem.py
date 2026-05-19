def DeductStockForItem(validated_items: list, product_stock_map: dict) -> bool:
    stock_updates = ComputeNewStock(validated_items, product_stock_map)
    success = UpdateStockInDB(stock_updates)
    return success