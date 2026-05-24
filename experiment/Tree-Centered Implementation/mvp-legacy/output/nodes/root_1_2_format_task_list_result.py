def format_task_list_result(filtered_tasks: list, status_filter: str) -> dict:
    """
    Format the filtered task list into the required result structure.
    
    Args:
        filtered_tasks: List of filtered tasks
        status_filter: Status filter that was applied
        
    Returns:
        dict: Formatted result dictionary with success status, message, and task list
    """
    # Validate preconditions
    if not isinstance(filtered_tasks, list):
        raise TypeError("filtered_tasks must be a list")
    
    # Create result dictionary structure
    result = {
        "success": True,
        "message": "",
        "tasks": filtered_tasks
    }
    
    # Generate appropriate success message based on task count and status filter
    task_count = len(filtered_tasks)
    
    if task_count == 0:
        if status_filter:
            result["message"] = f"No tasks found with status '{status_filter}'"
        else:
            result["message"] = "No tasks found"
    else:
        if status_filter:
            result["message"] = f"Found {task_count} task(s) with status '{status_filter}'"
        else:
            result["message"] = f"Found {task_count} task(s)"
    
    # Ensure postconditions are met
    assert "success" in result, "Result must contain 'success' key"
    assert "message" in result, "Result must contain 'message' key"
    assert "tasks" in result, "Result must contain 'tasks' key"
    assert result["tasks"] == filtered_tasks, "Result tasks must match filtered_tasks"
    
    return result