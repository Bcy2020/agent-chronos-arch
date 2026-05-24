def validate_task_exists(task_id: int, tasks: dict) -> tuple[bool, dict | None]:
    """
    Validate that the specified task exists in the tasks dictionary.
    
    Args:
        task_id: ID of the task to validate
        tasks: Current tasks dictionary with task IDs as keys
        
    Returns:
        tuple[bool, dict | None]: 
            - bool: True if task exists, False otherwise
            - dict | None: The task object if found, None otherwise
    """
    # Check if task_id exists in tasks dictionary
    if task_id in tasks:
        return True, tasks[task_id]
    else:
        return False, None