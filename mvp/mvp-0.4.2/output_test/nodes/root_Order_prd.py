def Order_prd(input: Any) -> Any:
    import json
    if isinstance(input, str):
        input = json.loads(input)
    command = input.get('command')
    order_data = input.get('order_data', {})
    if command == 'create_order':
        user_id = order_data.get('user_id')
        items = order_data.get('items')
        return CreateOrder(user_id, items)
    elif command == 'pay_order':
        order_id = order_data.get('order_id')
        user_id = order_data.get('user_id')
        return PayOrder(order_id, user_id)
    elif command == 'ship_order':
        order_id = order_data.get('order_id')
        return ShipOrder(order_id)
    elif command == 'complete_order':
        order_id = order_data.get('order_id')
        return CompleteOrder(order_id)
    elif command == 'cancel_order':
        order_id = order_data.get('order_id')
        return CancelOrder(order_id)
    elif command == 'list_orders':
        user_filter = order_data.get('user_filter')
        status_filter = order_data.get('status_filter')
        return ListOrders(user_filter, status_filter)
    elif command == 'get_user_orders':
        user_id = order_data.get('user_id')
        return GetUserOrders(user_id)
    elif command == 'list_products':
        low_stock = order_data.get('low_stock', False)
        return ListProducts(low_stock)
    else:
        return {'success': False, 'message': 'Unknown command', 'data': {}}