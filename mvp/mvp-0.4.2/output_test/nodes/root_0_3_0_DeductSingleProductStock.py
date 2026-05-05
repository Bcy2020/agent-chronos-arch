def DeductSingleProductStock(product_id: int, quantity: int, current_stock: int) -> bool:
    try:
        new_stock = current_stock - quantity
        update_product(product_id, {'stock': new_stock})
        return True
    except Exception:
        return False