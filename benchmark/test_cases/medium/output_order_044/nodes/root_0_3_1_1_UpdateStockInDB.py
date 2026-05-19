def UpdateStockInDB(stock_updates: list) -> bool:
    try:
        for update in stock_updates:
            product_id = update['product_id']
            new_stock = update['new_stock']
            result = update_product(product_id, {'stock': new_stock})
            if not result:
                return False
        return True
    except Exception:
        return False