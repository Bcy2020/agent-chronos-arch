def GetProductDetails(items: list) -> list:
    product_details = []
    for item in items:
        product = GetSingleProduct(item['product_id'])
        product_details.append(product)
    return product_details