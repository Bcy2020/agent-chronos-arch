def Order_prd(input: Any) -> Any:
    command, order_data = ParseInput(input)
    handler_name, handler_input = RouteCommand(command, order_data)
    if handler_name == 'CreateOrderHandler':
        result = CreateOrderHandler(handler_input)
    elif handler_name == 'PayOrderHandler':
        result = PayOrderHandler(handler_input)
    elif handler_name == 'ShipOrderHandler':
        result = ShipOrderHandler(handler_input)
    elif handler_name == 'CompleteOrderHandler':
        result = CompleteOrderHandler(handler_input)
    elif handler_name == 'CancelOrderHandler':
        result = CancelOrderHandler(handler_input)
    elif handler_name == 'ListOrdersHandler':
        result = ListOrdersHandler(handler_input)
    elif handler_name == 'GetUserOrdersHandler':
        result = GetUserOrdersHandler(handler_input)
    elif handler_name == 'ListProductsHandler':
        result = ListProductsHandler(handler_input)
    else:
        result = {'success': False, 'message': 'Unknown command', 'data': {}}
    return result