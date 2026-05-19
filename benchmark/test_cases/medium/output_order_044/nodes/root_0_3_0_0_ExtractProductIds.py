def ExtractProductIds(validated_items: list) -> list:
    return [item['product_id'] for item in validated_items]