def DeleteTask(task_id: int) -> dict:
    global tasks
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            del tasks[i]
            return {'success': True, 'message': 'Task deleted successfully.', 'data': None}
    return {'success': False, 'message': 'Task not found.', 'data': None}