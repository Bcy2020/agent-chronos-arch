def ValidateInputType(input: Any) -> Tuple[str, Optional[str]]:
    """
    Validate that the input is a string. If not, attempt to convert it to a string.
    Returns a tuple of (validated_input, validation_error).
    """
    if isinstance(input, str):
        return input, None
    try:
        converted = str(input)
        return converted, None
    except Exception:
        return "", "Input is not a string and cannot be converted"