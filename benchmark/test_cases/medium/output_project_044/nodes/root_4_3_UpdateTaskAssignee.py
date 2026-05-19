def UpdateTaskAssignee(task_id: int, member_id: int) -> dict:
    if not ValidateTaskExists(task_id):
        raise ValueError(f"Task {task_id} does not exist")
    if not ValidateMemberExists(member_id):
        raise ValueError(f"Member {member_id} does not exist")
    return UpdateTaskAssignee(task_id, member_id)