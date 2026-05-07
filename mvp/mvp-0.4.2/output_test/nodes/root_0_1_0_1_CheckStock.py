def CheckStock(product: Optional[dict], quantity: int) -> Tuple[bool, Optional[str]]:
    if product is None:
        return (False, 'Product not found')
    if product['stock'] < quantity:
        return (False, 'Insufficient stock')
    return (True, None)