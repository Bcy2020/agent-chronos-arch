def CheckProductStock(items: list) -> bool:
    # Access the global products list
    global products
    for item in items:
        product_id = item.get('product_id')
        quantity = item.get('quantity', 0)
        # Find product in products list
        product = None
        for p in products:
            if p['product_id'] == product_id:
                product = p
                break
        if product is None:
            return False
        if product['stock'] < quantity:
            return False
    return True