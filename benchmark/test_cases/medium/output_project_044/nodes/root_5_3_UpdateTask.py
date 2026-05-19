def UpdateTask(task_id: int, new_status: str, additional_updates: dict) -> dict:
    updates = {'status': new_status}
    updates.update(additional_updates)
    result = update_task(task_id, updates)
    return result