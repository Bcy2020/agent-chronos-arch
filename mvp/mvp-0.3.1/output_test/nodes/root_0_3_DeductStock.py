def DeductStock(items: list) -> bool:
    global products
    for item in items:
        product_id = item.get('product_id')
        quantity = item.get('quantity')
        if product_id is None or quantity is None:
            return False
        for product in products:
            if product['product_id'] == product_id:
                product['stock'] -= quantity
                break
        else:
            return False
    return True