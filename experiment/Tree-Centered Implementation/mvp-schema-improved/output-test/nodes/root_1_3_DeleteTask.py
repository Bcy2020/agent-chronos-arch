def DeleteTask(task_data: dict, tasks: list) -> Tuple[dict, list]:
    task_id = task_data['id']
    found_task, task_index = FindTaskById(task_id, tasks)
    if found_task is None:
        return {'success': False, 'message': f'Task {task_id} not found', 'deleted_task': None}, tasks
    updated_tasks, deleted_task = RemoveTaskFromList(tasks, task_index, found_task)
    result = BuildDeleteResult(deleted_task, task_id)
    return result, updated_tasks