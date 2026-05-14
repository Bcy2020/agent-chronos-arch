def CalculateTotal(items: list, product_details: list) -> float:
    total = 0.0
    for item, product in zip(items, product_details):
        quantity = item.get('quantity', 0)
        price = product.get('price', 0.0)
        total += quantity * price
    return total