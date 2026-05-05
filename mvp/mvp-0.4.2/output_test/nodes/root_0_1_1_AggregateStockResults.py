from typing import Tuple, List, Any

def AggregateStockResults(items: list, product_details_list: list, stock_ok_list: list) -> Tuple[bool, list]:
    overall_stock_ok = True
    product_details = []
    for i, stock_ok in enumerate(stock_ok_list):
        if not stock_ok:
            overall_stock_ok = False
        else:
            product_details.append(product_details_list[i])
    return overall_stock_ok, product_details