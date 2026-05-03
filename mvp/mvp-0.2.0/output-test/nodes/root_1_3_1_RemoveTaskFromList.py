def RemoveTaskFromList(tasks: list, task_index: int, found_task: dict) -> Tuple[list, dict]:
    """
    Removes the task at the given index from the tasks list and returns the updated list and the removed task.
    """
    updated_tasks = tasks.copy()
    deleted_task = updated_tasks.pop(task_index)
    return updated_tasks, deleted_task