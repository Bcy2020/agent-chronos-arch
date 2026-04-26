def AppendTaskToList(new_task: dict, tasks: list) -> list:
    """
    Appends the new task to the tasks list and returns the updated list.
    
    Args:
        new_task: The created task dictionary
        tasks: Current list of tasks
    
    Returns:
        Updated list of tasks with new task appended
    """
    updated_tasks = tasks.copy()
    updated_tasks.append(new_task)
    return updated_tasks