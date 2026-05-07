def ListProducts(order_data: dict) -> dict:
    products = ListAllProducts()
    low_stock = order_data.get('low_stock', False)
    filtered_products = FilterLowStockProducts(products, low_stock)
    return {'success': True, 'data': {'products': filtered_products}}