def FindTaskById(task_id: int, tasks: list) -> Tuple[Optional[dict], Optional[int]]:
    """
    Searches the tasks list for a task matching the given ID and returns the task and its index.

    Args:
        task_id: ID of the task to find
        tasks: Current list of tasks

    Returns:
        Tuple of (found_task, task_index) where found_task is the task dict or None,
        and task_index is the index in the list or None.
    """
    for index, task in enumerate(tasks):
        if task.get('id') == task_id:
            return task, index
    return None, None