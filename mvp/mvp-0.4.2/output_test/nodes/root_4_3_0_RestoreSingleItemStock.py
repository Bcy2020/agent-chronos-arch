def RestoreSingleItemStock(item: dict) -> Tuple[bool, str]:
    product_id = item.get('product_id')
    quantity = item.get('quantity')
    if product_id is None or quantity is None:
        return False, "Missing 'product_id' or 'quantity' in item"
    product = get_product(product_id)
    if product is None:
        return False, f"Product with id {product_id} not found"
    current_stock = product['stock']
    new_stock = current_stock + quantity
    if new_stock < 0:
        return False, "Resulting stock cannot be negative"
    update_product(product_id, {'stock': new_stock})
    return True, ""