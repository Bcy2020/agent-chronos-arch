def remove_task_from_dict(task_id: int, tasks: dict) -> bool:
    """
    Remove a task from the tasks dictionary by its ID.
    
    Args:
        task_id: ID of the task to remove
        tasks: Tasks dictionary to modify (will be modified in place)
    
    Returns:
        True if task was removed, False otherwise
    """
    try:
        # Check if task_id exists in the dictionary
        if task_id in tasks:
            # Remove the task by its ID
            del tasks[task_id]
            return True
        else:
            # Task ID not found in dictionary
            return False
    except Exception as e:
        # Handle any unexpected errors (e.g., tasks is not a dictionary)
        # Log the error if needed, but return False as removal failed
        return False