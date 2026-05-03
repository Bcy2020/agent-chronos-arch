def ExtractTaskData(parsed_data: Optional[dict]) -> Optional[dict]:
    has_task_data = CheckTaskDataPresence(parsed_data)
    task_data = ExtractTaskDataValue(parsed_data, has_task_data)
    return task_data