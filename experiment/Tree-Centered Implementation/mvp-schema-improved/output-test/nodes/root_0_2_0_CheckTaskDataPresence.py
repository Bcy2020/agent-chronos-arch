def CheckTaskDataPresence(parsed_data: Optional[dict]) -> bool:
    if parsed_data is None:
        return False
    return 'task_data' in parsed_data