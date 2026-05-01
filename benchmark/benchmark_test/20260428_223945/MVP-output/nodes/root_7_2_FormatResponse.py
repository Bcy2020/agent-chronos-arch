def FormatResponse(filtered_products: list) -> dict:
    return {
        'success': True,
        'message': 'Products listed successfully',
        'data': filtered_products
    }