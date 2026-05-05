def CalculateTotalPrice(product_details: list) -> float:
    total = 0.0
    for item in product_details:
        total += item['price'] * item['quantity']
    return total