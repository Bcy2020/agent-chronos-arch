def GetProductStock(product_id: int) -> int:
    product = get_product(product_id)
    return product['stock']