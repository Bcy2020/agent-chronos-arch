def create_error_response(task_id: int, error_message: str) -> dict:
    """
    Create an error response dictionary for a failed task completion operation.
    
    Args:
        task_id: ID of the task that was not found
        error_message: Description of the error
        
    Returns:
        dict: Error response dictionary with error details
        
    Preconditions:
        - Task ID is provided
        - Error message is provided
    """
    
    # Validate inputs (basic validation as per preconditions)
    if not isinstance(task_id, int):
        raise TypeError("task_id must be an integer")
    
    if not isinstance(error_message, str):
        raise TypeError("error_message must be a string")
    
    if not error_message.strip():
        raise ValueError("error_message cannot be empty")
    
    # Create error response dictionary
    error_response = {
        "success": False,
        "task_id": task_id,
        "error": {
            "message": error_message,
            "type": "TaskCompletionError",
            "timestamp": datetime.datetime.now().isoformat()
        },
        "status": "failed",
        "suggestions": [
            "Verify the task ID exists",
            "Check if the task is already completed",
            "Ensure you have proper permissions"
        ]
    }
    
    return error_response