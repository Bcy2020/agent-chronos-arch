def CombineParseResults(parse_error: Optional[str], command: Optional[str], validation_error: Optional[str], task_data: Optional[dict]) -> Tuple[Optional[str], Optional[dict], Optional[str]]:
    # Check parse_error first; if present, return None for command and task_data with parse_error
    if parse_error is not None:
        return None, None, parse_error
    # Else check validation_error; if present, return None for command and task_data with validation_error
    if validation_error is not None:
        return None, None, validation_error
    # Else return command, task_data, and None error
    return command, task_data, None