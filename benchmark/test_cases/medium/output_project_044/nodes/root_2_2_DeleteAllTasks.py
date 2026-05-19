def DeleteAllTasks(task_ids: list) -> bool:
    for task_id in task_ids:
        if not DeleteSingleTask(task_id):
            return False
    return True