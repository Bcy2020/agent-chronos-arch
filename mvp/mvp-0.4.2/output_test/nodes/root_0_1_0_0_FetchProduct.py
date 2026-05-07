def FetchProduct(product_id: int) -> Optional[dict]:
    try:
        return get_product(product_id)
    except Exception:
        return None