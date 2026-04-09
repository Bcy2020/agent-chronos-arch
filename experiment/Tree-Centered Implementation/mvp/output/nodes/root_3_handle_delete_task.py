def handle_delete_task(task_data: dict, tasks: dict) -> dict:
    """Remove a specific task from memory storage."""
    # Extract task_id from input data
    task_id = task_data.get('task_id')
    
    # Validate that the task exists
    exists = validate_task_exists(task_id, tasks)
    
    if exists:
        # Remove the task from the dictionary
        removed = remove_task_from_dict(task_id, tasks)
        if removed:
            # Create success response
            return create_success_response(task_id)
        else:
            # This should not happen if validation passed, but handle gracefully
            return create_error_response(task_id)
    else:
        # Task doesn't exist, return error response
        return create_error_response(task_id)