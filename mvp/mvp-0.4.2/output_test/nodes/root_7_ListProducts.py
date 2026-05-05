def ListProducts(low_stock: bool) -> Tuple[bool, str, dict]:
    products = FetchProducts(low_stock)
    return True, "Products retrieved successfully", {"products": products}