def RestoreStock(order: dict) -> bool:
    items = GetOrderItems(order)
    results = []
    for item in items:
        product_id = item['product_id']
        quantity = item['quantity']
        result = RestoreStockForItem(product_id, quantity)
        results.append(result)
    return AggregateResults(results)