def BuildDeleteResult(deleted_task: dict, task_id: int) -> dict:
    result = {
        'success': True,
        'message': f'Task {task_id} deleted successfully',
        'deleted_task': deleted_task
    }
    return result