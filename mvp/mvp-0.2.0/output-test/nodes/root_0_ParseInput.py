def ParseInput(input: Any) -> Tuple[str, Optional[dict], Optional[str]]:
    parsed_data, parse_error = ParseJsonInput(input)
    command, validation_error = ValidateAndExtractCommand(parsed_data)
    task_data = ExtractTaskData(parsed_data)
    final_command, final_task_data, final_error = CombineParseResults(parse_error, command, validation_error, task_data)
    return final_command, final_task_data, final_error