def ExtractTaskDataValue(parsed_data: Optional[dict], has_task_data: bool) -> Optional[dict]:
    if has_task_data and parsed_data is not None and 'task_data' in parsed_data:
        return parsed_data['task_data']
    return None