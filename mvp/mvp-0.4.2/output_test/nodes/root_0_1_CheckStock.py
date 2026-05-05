def CheckStock(items: list) -> Tuple[bool, list]:
    product_details_list = []
    stock_ok_list = []
    for item in items:
        product_id = item['product_id']
        quantity = item['quantity']
        details, ok = GetProductDetails(product_id, quantity)
        product_details_list.append(details)
        stock_ok_list.append(ok)
    stock_ok, product_details = AggregateStockResults(items, product_details_list, stock_ok_list)
    return stock_ok, product_details