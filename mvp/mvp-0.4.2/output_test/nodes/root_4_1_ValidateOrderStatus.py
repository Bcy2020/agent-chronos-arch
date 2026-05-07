from typing import Tuple

def ValidateOrderStatus(order: dict) -> Tuple[bool, str]:
    if order is None:
        return False, 'Order not found'
    if order.get('status') not in ['pending', 'paid']:
        return False, 'Order cannot be cancelled'
    return True, ''