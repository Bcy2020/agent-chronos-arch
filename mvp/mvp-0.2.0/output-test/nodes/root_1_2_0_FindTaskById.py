def FindTaskById(task_id: int, tasks: list) -> Tuple[Optional[dict], int]:
    """
    Searches the tasks list for a task with the given ID and returns it if found.

    Args:
        task_id: ID of the task to find
        tasks: Current list of tasks

    Returns:
        A tuple of (found_task, task_index) where found_task is the task dict or None,
        and task_index is the index of the task in the list (or -1 if not found).
    """
    # Perform the read operation on the global tasks variable (op_root_0_read)
    # The condition 'id == task_id' is applied during iteration
    for index, task in enumerate(tasks):
        if task.get('id') == task_id:
            return task, index
    return None, -1