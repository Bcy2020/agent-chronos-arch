def CompleteTask(task_id: int) -> dict:
    global tasks
    for task in tasks:
        if task['id'] == task_id:
            task['status'] = 'completed'
            return {"success": True, "message": "Task completed successfully.", "data": task}
    return {"success": False, "message": "Task not found.", "data": None}