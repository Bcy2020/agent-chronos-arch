def ExtractCommand(valid_data: Optional[dict]) -> Tuple[Optional[str], Optional[str]]:
    if 'command' not in valid_data:
        return None, 'Missing command field'
    return valid_data['command'], None