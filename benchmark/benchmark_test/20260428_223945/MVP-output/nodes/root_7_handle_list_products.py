def handle_list_products(order_data: dict) -> dict:
    products = ReadProducts()
    filtered_products = FilterLowStock(products, order_data)
    result = FormatResponse(filtered_products)
    return result