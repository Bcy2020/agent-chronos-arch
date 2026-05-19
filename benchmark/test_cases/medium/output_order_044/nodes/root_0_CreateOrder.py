def CreateOrder(order_data: dict) -> dict:
    user_id = order_data.get('user_id')
    items = order_data.get('items')
    if not user_id or not items:
        return {'success': False, 'message': 'Invalid order data', 'data': None}
    if not ValidateUser(user_id):
        return {'success': False, 'message': 'User not found', 'data': None}
    products_valid, validated_items = ValidateProducts(items)
    if not products_valid:
        return {'success': False, 'message': 'Product validation failed', 'data': None}
    total_price = CalculateTotal(validated_items)
    if not DeductStock(validated_items):
        return {'success': False, 'message': 'Stock deduction failed', 'data': None}
    order_id = CreateOrderRecord(user_id, items, total_price)
    return {'success': True, 'message': 'Order created', 'data': {'order_id': order_id, 'total_price': total_price}}