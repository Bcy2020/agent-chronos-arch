def CompleteTask(task_data: dict, tasks: list) -> Tuple[dict, list]:
    task_id = task_data.get('id')
    found_task, task_index = FindTaskById(task_id, tasks)
    updated_task, updated_tasks = UpdateTaskStatus(found_task, task_index, tasks)
    if updated_task is not None:
        result = {'success': True, 'message': 'Task completed successfully', 'task': updated_task}
    else:
        result = {'success': False, 'message': 'Task not found', 'task': None}
    return result, updated_tasks