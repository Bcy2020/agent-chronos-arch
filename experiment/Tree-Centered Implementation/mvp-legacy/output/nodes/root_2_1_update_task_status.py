def update_task_status(task: dict, tasks: dict) -> dict:
    """
    Update the status of a task to 'completed'.
    
    Args:
        task: Task object to update
        tasks: Current tasks dictionary
        
    Returns:
        Task with updated status
    """
    # Update the task status
    task['status'] = 'completed'
    
    # Update the tasks dictionary if the task has an ID
    if 'id' in task:
        task_id = task['id']
        if task_id in tasks:
            tasks[task_id] = task
    
    return task