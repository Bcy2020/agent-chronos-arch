def FetchProductStocks(product_ids: list) -> dict:
    product_stock_map = {}
    for pid in product_ids:
        product = get_product(pid)
        if product is not None:
            product_stock_map[pid] = product['stock']
    return product_stock_map