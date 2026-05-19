def CheckStockSufficiency(product: Optional[dict], quantity: int) -> bool:
    if product is None:
        return False
    return product.get('stock', 0) >= quantity