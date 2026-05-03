def CreateTask(task_data: dict, tasks: list, next_id: dict) -> Tuple[dict, list, dict]:
    new_id, updated_next_id = GenerateTaskId(next_id)
    new_task = CreateTaskDict(new_id, task_data)
    updated_tasks = AppendTaskToList(new_task, tasks)
    result = FormatCreateTaskResult(new_task)
    return result, updated_tasks, updated_next_id