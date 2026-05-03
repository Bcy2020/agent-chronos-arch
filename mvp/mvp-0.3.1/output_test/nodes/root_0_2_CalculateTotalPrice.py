def CalculateTotalPrice(items: list) -> float:
    total_price = 0.0
    for item in items:
        product_id = item.get('product_id')
        quantity = item.get('quantity', 0)
        # Look up product price from global products list
        product = next((p for p in products if p['id'] == product_id), None)
        if product:
            total_price += product['price'] * quantity
    return total_price