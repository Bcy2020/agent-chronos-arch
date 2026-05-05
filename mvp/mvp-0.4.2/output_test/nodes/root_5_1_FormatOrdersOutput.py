def FormatOrdersOutput(orders_list: list) -> Tuple[bool, str, dict]:
    return (True, 'Orders retrieved successfully', {'orders': orders_list})