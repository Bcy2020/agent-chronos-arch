def create_error_response(task_id: int) -> dict:
    """
    Create an error response dictionary for a non-existent task.
    
    Args:
        task_id: ID of the non-existent task
        
    Returns:
        Dictionary containing error status and appropriate message
    """
    # Validate input type (though preconditions say it's valid integer)
    if not isinstance(task_id, int):
        raise TypeError(f"task_id must be an integer, got {type(task_id).__name__}")
    
    # Create the error response dictionary
    response = {
        "status": "error",
        "error_code": "TASK_NOT_FOUND",
        "message": f"Task with ID {task_id} does not exist",
        "task_id": task_id,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    return response