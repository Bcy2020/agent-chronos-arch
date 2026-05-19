def FetchTask(task_id: int) -> dict:
    task = get_task(task_id)
    if task is None:
        raise ValueError(f"Task with id {task_id} not found")
    return task