def CreateOrder(order_data: dict) -> dict:
    user_id = order_data.get('user_id')
    items = order_data.get('items', [])
    if not user_id or not items:
        return {'error': 'Invalid order data'}
    if not ValidateUser(user_id):
        return {'error': 'User not found'}
    stock_valid, product_details = ValidateStock(items)
    if not stock_valid:
        return {'error': 'Insufficient stock'}
    total_price = CalculateTotal(items, product_details)
    if not DeductStock(items, product_details):
        return {'error': 'Stock deduction failed'}
    order_id = CreateOrderRecord(user_id, items, total_price)
    return {'success': True, 'order_id': order_id, 'total_price': total_price}