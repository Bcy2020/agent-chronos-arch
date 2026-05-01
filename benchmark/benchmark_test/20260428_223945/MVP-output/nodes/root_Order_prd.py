def Order_prd(input: Any) -> Any:
    command = input.get('command')
    order_data = input.get('order_data', {})
    if command == 'create_order':
        return handle_create_order(order_data)
    elif command == 'pay_order':
        return handle_pay_order(order_data)
    elif command == 'ship_order':
        return handle_ship_order(order_data)
    elif command == 'complete_order':
        return handle_complete_order(order_data)
    elif command == 'cancel_order':
        return handle_cancel_order(order_data)
    elif command == 'list_orders':
        return handle_list_orders(order_data)
    elif command == 'get_user_orders':
        return handle_get_user_orders(order_data)
    elif command == 'list_products':
        return handle_list_products(order_data)
    else:
        return {'success': False, 'message': 'Unknown command'}