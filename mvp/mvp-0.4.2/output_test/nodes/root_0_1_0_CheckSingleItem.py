def CheckSingleItem(product_id: int, quantity: int) -> Tuple[bool, Optional[str]]:
    product = FetchProduct(product_id)
    return CheckStock(product, quantity)