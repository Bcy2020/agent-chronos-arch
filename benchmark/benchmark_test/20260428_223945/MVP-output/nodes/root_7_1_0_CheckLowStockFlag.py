def CheckLowStockFlag(order_data: dict) -> bool:
    return order_data.get('low_stock', False) is True