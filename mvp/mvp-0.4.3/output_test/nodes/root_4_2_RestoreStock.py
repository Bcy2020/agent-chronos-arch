def RestoreStock(order: dict) -> bool:
    try:
        for item in order['items']:
            product_id = item['product_id']
            quantity = item['quantity']
            product = get_product(product_id)
            if product is None:
                return False
            current_stock = product['stock']
            update_product(product_id, {'stock': current_stock + quantity})
        return True
    except Exception:
        return False