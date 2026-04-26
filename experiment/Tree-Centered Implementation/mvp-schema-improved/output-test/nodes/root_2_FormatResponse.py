def FormatResponse(result: dict, parse_error: Optional[str]) -> Any:
    error_json = HandleParseError(parse_error)
    return FormatSuccessResponse(result, error_json)