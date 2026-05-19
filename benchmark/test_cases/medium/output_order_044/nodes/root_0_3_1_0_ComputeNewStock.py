def ComputeNewStock(validated_items: list, product_stock_map: dict) -> list:
    stock_updates = []
    for item in validated_items:
        product_id = item['product_id']
        quantity = item['quantity']
        new_stock = product_stock_map[product_id] - quantity
        stock_updates.append({'product_id': product_id, 'new_stock': new_stock})
    return stock_updates