def CalculateTotal(items: list, products_data: list) -> float:
    total = 0.0
    for item, product in zip(items, products_data):
        price = product.get('price', 0)
        quantity = item.get('quantity', 0)
        total += price * quantity
    return total