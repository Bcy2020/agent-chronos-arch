def UpdateTaskStatus(project_data: dict) -> dict:
    task_id = project_data.get('task_id')
    new_status = project_data.get('new_status')
    actual_hours = project_data.get('actual_hours')
    try:
        task = GetTask(task_id)
    except Exception as e:
        return {'success': False, 'message': str(e)}
    current_status = task['status']
    is_valid, error_message = ValidateTransition(current_status, new_status)
    if not is_valid:
        return {'success': False, 'message': error_message}
    additional_updates = RecordActualHours(new_status, actual_hours)
    result = UpdateTask(task_id, new_status, additional_updates)
    return result