def RestoreStock(order: dict) -> bool:
    for item in order['items']:
        product_id = item['product_id']
        current_stock = GetProductStock(product_id)
        new_stock = current_stock + item['quantity']
        if not UpdateProductStock(product_id, new_stock):
            return False
    return True