def ValidateProducts(items: list) -> Tuple[bool, list]:
    products_valid = True
    validated_items = []
    for item in items:
        product_id = item['product_id']
        quantity = item['quantity']
        product = CheckProductExistence(product_id)
        if product is None:
            products_valid = False
        else:
            stock_sufficient = CheckStockSufficiency(product, quantity)
            if not stock_sufficient:
                products_valid = False
            else:
                validated_items.append({'product_id': product_id, 'name': product['name'], 'price': product['price'], 'quantity': quantity})
    return (products_valid, validated_items)