def NormalizeFilters(input: dict) -> dict:
    filters = ParseFilters(input)
    if 'tags' not in filters:
        filters['tags'] = []
    validated_filters = ValidateFilters(filters)
    result = FormatFilters(validated_filters)
    return result