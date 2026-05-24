def filter_tasks_by_status(tasks: dict, status_filter: str) -> list:
    """
    Filter tasks dictionary based on status filter criteria.
    
    Args:
        tasks: Dictionary of tasks where keys are task IDs and values are task dictionaries
        status_filter: Status filter value ('pending', 'completed', or None)
        
    Returns:
        List of task dictionaries matching the filter criteria
        
    Raises:
        TypeError: If tasks is not a dictionary
        ValueError: If status_filter has an invalid value
    """
    # Validate preconditions
    if not isinstance(tasks, dict):
        raise TypeError("tasks must be a dictionary")
    
    if status_filter not in ['pending', 'completed', None]:
        raise ValueError("status_filter must be 'pending', 'completed', or None")
    
    # Initialize result list
    filtered_tasks = []
    
    # Iterate through tasks dictionary
    for task_id, task_details in tasks.items():
        # Validate task structure
        if not isinstance(task_details, dict):
            continue  # Skip invalid task entries
            
        # Apply status filter logic
        if status_filter is None:
            # Include all tasks when no filter is specified
            filtered_tasks.append({
                'id': task_id,
                **task_details
            })
        else:
            # Check if task has a status field and it matches the filter
            if 'status' in task_details and task_details['status'] == status_filter:
                filtered_tasks.append({
                    'id': task_id,
                    **task_details
                })
    
    return filtered_tasks