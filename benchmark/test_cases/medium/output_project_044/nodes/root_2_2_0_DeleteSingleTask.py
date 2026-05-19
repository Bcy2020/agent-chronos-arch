def DeleteSingleTask(task_id: int) -> bool:
    try:
        delete_task(task_id)
        return True
    except Exception:
        return False