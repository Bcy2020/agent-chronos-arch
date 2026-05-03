def RestoreStock(order: dict) -> bool:
    for item in order['items']:
        product_id = item['product_id']
        quantity = item['quantity']
        found = False
        for product in products:
            if product['id'] == product_id:
                product['stock'] += quantity
                found = True
                break
        if not found:
            raise Exception(f"Product {product_id} not found")
    return True