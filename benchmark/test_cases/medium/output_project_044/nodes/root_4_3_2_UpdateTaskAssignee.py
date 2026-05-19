def UpdateTaskAssignee(task_id: int, member_id: int) -> dict:
    updates = {'assignee_id': member_id}
    updated_task = update_task(task_id, updates)
    return updated_task