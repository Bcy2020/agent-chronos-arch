def CheckStockSufficiency(items: list, product_details: list) -> Tuple[bool, list]:
    stock_valid = True
    valid_product_details = []
    for item, product in zip(items, product_details):
        if product is None or product['stock'] < item['quantity']:
            stock_valid = False
            valid_product_details = []
            break
        valid_product_details.append(product)
    return stock_valid, valid_product_details