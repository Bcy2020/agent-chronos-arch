def UpdateProductStock(product_id: int, new_stock: int) -> bool:
    try:
        update_product(product_id, {'stock': new_stock})
        return True
    except Exception:
        return False