def CheckParsedData(parsed_data: Optional[dict]) -> Tuple[Optional[dict], Optional[str]]:
    if parsed_data is None:
        return None, 'Invalid input: parsed data is None'
    return parsed_data, None