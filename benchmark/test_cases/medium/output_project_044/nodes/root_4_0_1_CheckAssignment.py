def CheckAssignment(task: dict, allow_reassign: bool) -> dict:
    if task.get('assignee_id') is not None and not allow_reassign:
        raise ValueError('Task is assigned and reassign is not allowed')
    return task