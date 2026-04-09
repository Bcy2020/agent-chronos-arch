def validate_task_exists(task_id: int, tasks: dict[int, dict]) -> bool:
    """
    Validate that the specified task exists in the tasks dictionary.
    
    Args:
        task_id: ID of the task to validate
        tasks: Current tasks dictionary
        
    Returns:
        True if task exists, False otherwise
    """
    # Precondition check: tasks dictionary is not None
    if tasks is None:
        raise ValueError("tasks dictionary cannot be None")
    
    # Check if task_id exists as key in tasks dictionary
    exists = task_id in tasks
    
    return exists