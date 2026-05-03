def HandleParseError(parse_error: Optional[str]) -> Optional[dict]:
    if parse_error is not None:
        return {'success': False, 'message': parse_error}
    return None