def handle_complete_task(task_data: dict, tasks: dict) -> dict:
    """Mark a specific task as completed by updating its status in memory."""
    # Extract task_id from input data
    task_id = task_data.get('task_id')
    
    # Validate that the task exists
    exists, task = validate_task_exists(task_id, tasks)
    
    if exists:
        # Update the task status to 'completed'
        updated_task = update_task_status(task, tasks)
        
        # Create success response
        result = create_success_response(task_id, updated_task)
    else:
        # Create error response for non-existent task
        error_msg = f"Task with ID {task_id} not found"
        result = create_error_response(task_id, error_msg)
    
    return result