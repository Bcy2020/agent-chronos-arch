def Order_prd(input: Any) -> Any:
    command, order_data = ParseInput(input)
    if command == 'create_order':
        return CreateOrder(order_data)
    elif command == 'pay_order':
        return PayOrder(order_data)
    elif command == 'ship_order':
        return ShipOrder(order_data)
    elif command == 'complete_order':
        return CompleteOrder(order_data)
    elif command == 'cancel_order':
        return CancelOrder(order_data)
    elif command == 'list_orders':
        return ListOrders(order_data)
    elif command == 'get_user_orders':
        return GetUserOrders(order_data)
    elif command == 'list_products':
        return ListProducts(order_data)
    else:
        return {'success': False, 'message': 'Unknown command'}