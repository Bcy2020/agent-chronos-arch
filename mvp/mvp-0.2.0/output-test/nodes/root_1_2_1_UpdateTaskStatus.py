def UpdateTaskStatus(found_task: Optional[dict], task_index: int, tasks: list) -> Tuple[Optional[dict], list]:
    if found_task is not None:
        updated_task = found_task.copy()
        updated_task['status'] = 'completed'
        tasks[task_index] = updated_task
        return updated_task, tasks
    else:
        return None, tasks