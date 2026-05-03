def FormatCreateTaskResult(new_task: dict) -> dict:
    result = {
        'success': True,
        'message': 'Task created successfully',
        'task': new_task
    }
    return result