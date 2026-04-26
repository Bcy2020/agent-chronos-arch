def ValidateAndExtractCommand(parsed_data: Optional[dict]) -> Tuple[Optional[str], Optional[str]]:
    # Step 1: Check if parsed_data is None
    valid_data, error = CheckParsedData(parsed_data)
    if error is not None:
        return None, error
    
    # Step 2: Extract the 'command' key
    command_value, error = ExtractCommand(valid_data)
    if error is not None:
        return None, error
    
    # Step 3: Validate the command value
    command, validation_error = ValidateCommand(command_value)
    return command, validation_error