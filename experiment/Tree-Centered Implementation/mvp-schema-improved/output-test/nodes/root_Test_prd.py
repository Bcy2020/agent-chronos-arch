def Test_prd(input: Any) -> Any:
    # Step 1: Parse the input
    command, task_data, parse_error = ParseInput(input)
    
    # Step 2: If there's a parse error, format error response and return
    if parse_error is not None:
        return FormatResponse({}, parse_error)
    
    # Step 3: Execute the command
    result = ExecuteCommand(command, task_data)
    
    # Step 4: Format and return the response
    return FormatResponse(result, None)