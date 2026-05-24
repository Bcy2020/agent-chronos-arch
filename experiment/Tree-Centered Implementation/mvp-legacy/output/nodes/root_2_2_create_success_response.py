def create_success_response(task_id: int, task: dict) -> dict:
    """
    Create a success response dictionary for a completed task operation.
    
    Args:
        task_id: ID of the completed task
        task: Updated task object
        
    Returns:
        Success response dictionary with task details
    """
    # Create the success response dictionary
    response = {
        "status": "success",
        "message": "Task operation completed successfully",
        "task_id": task_id,
        "task": task,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    return response