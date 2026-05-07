def CreateOrder(order_data: dict) -> dict:
    user_id = order_data.get('user_id')
    items = order_data.get('items', [])
    if not user_id or not items:
        return {'success': False, 'error': 'Invalid order data'}
    user = ValidateUser(user_id)
    if user is None:
        return {'success': False, 'error': 'User not found'}
    stock_ok, error = CheckStock(items)
    if not stock_ok:
        return {'success': False, 'error': error}
    products_data = []
    for item in items:
        product = products.get(item['product_id'])
        products_data.append(product)
    total_price = CalculateTotal(items, products_data)
    deduct_ok, deduct_error = DeductStock(items)
    if not deduct_ok:
        return {'success': False, 'error': deduct_error}
    order = CreateOrderRecord(order_data, total_price)
    return {'success': True, 'order_id': order['order_id'], 'total_price': total_price}