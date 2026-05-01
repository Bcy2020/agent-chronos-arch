def UpdateOrderStatusInStore(order: dict) -> bool:
    updated_order = SetOrderStatusToPaid(order)
    success = WriteUpdatedOrderToStore(updated_order)
    return success