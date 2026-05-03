def ExecuteCommand(command: str, task_data: Optional[dict]) -> dict:
    global tasks, next_id

    if command == 'create':
        result, updated_tasks, updated_next_id = CreateTask(task_data, tasks, next_id)
        tasks, next_id = updated_tasks, updated_next_id
        return result
    elif command == 'list':
        return ListTasks(task_data, tasks)
    elif command == 'complete':
        result, updated_tasks = CompleteTask(task_data, tasks)
        tasks = updated_tasks
        return result
    elif command == 'delete':
        result, updated_tasks = DeleteTask(task_data, tasks)
        tasks = updated_tasks
        return result
    else:
        return {'success': False, 'message': f'Unknown command: {command}', 'data': None}