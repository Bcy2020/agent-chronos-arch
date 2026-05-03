def FilterTasksByStatus(tasks_list: list, task_data: Optional[dict]) -> list:
    """
    Filters the tasks list by status if a status filter is provided in task_data.
    
    Args:
        tasks_list: Full list of tasks to filter
        task_data: Optional filter data containing status key
    
    Returns:
        Filtered list of tasks (or full list if no filter)
    """
    if task_data is not None and 'status_filter' in task_data:
        status_filter = task_data['status_filter']
        if status_filter == 'all':
            return tasks_list.copy()
        return [task for task in tasks_list if task.get('status') == status_filter]
    return tasks_list.copy()