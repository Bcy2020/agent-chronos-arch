def DeductStock(items: list, product_details: list) -> bool:
    for item, detail in zip(items, product_details):
        product_id = item['product_id']
        quantity = item['quantity']
        current_stock = detail['stock']
        if not DeductSingleProductStock(product_id, quantity, current_stock):
            return False
    return True