def ParseJsonInput(input: Any) -> Tuple[Optional[dict], Optional[str]]:
    validated_input, validation_error = ValidateInputType(input)
    if validation_error is not None:
        return None, validation_error
    parsed_data, parse_error = ParseJsonString(validated_input)
    return parsed_data, parse_error