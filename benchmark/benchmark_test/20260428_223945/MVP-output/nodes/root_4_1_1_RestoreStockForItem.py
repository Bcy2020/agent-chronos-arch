def RestoreStockForItem(product_id: int, quantity: int) -> bool:
    # Access the global products list
    global products
    # Iterate through products to find the one with matching product_id
    for product in products:
        if product['product_id'] == product_id:
            # Increase stock by quantity
            product['stock'] += quantity
            return True
    # Product not found
    return False