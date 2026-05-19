def DeductStock(validated_items: list) -> bool:
    product_stock_map = GetProductStock(validated_items)
    success = DeductStockForItem(validated_items, product_stock_map)
    return success