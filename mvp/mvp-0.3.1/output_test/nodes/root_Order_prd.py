def Order_prd(input: Any) -> Any:
    try:
        command = input.get('command')
        order_data = input.get('order_data', {})
        if command == 'create_order':
            user_id = order_data.get('user_id')
            items = order_data.get('items', [])
            return CreateOrder(user_id, items)
        elif command == 'pay_order':
            order_id = order_data.get('order_id')
            return PayOrder(order_id)
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
            orders = ListOrders(user_filter, status_filter)
            return {'success': True, 'message': '查询成功', 'data': {'orders': orders}}
        elif command == 'get_user_orders':
            user_id = order_data.get('user_id')
            result = GetUserOrders(user_id)
            return {'success': True, 'message': '查询成功', 'data': result}
        elif command == 'list_products':
            low_stock = order_data.get('low_stock', False)
            products = ListProducts(low_stock)
            return {'success': True, 'message': '查询成功', 'data': {'products': products}}
        else:
            return {'success': False, 'message': '未知命令', 'data': {}}
    except Exception as e:
        return {'success': False, 'message': str(e), 'data': {}}