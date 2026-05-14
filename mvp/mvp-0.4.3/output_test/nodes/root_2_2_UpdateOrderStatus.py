def UpdateOrderStatus(order_data: dict) -> dict:
    try:
        order_id = order_data['order_id']
        result = update_order(order_id, {'status': 'shipped'})
        if result.get('success'):
            return {'success': True}
        else:
            return result
    except Exception as e:
        return {'error': str(e)}