def CalculateTotal(validated_items: list) -> float:
    total = 0.0
    for item in validated_items:
        total += item['price'] * item['quantity']
    return total