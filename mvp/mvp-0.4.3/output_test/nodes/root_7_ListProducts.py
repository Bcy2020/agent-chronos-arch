def ListProducts(order_data: dict) -> dict:
    products_list = GetAllProducts()
    filtered_products = FilterLowStockProducts(products_list, order_data)
    return {"success": True, "products": filtered_products}