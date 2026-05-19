def ValidateTask(task_id: int, allow_reassign: bool) -> dict:
    task = GetTask(task_id)
    return CheckAssignment(task, allow_reassign)