def format_create_response(success: bool, message: str, task_object: dict = None) -> dict:
    """
    Format the success or error response for the create task operation.
    
    Args:
        success: Whether the operation succeeded
        message: Success or error message
        task_object: Created task object (if successful)
        
    Returns:
        dict: Formatted operation result dictionary with success, message, and data fields
    """
    # Validate preconditions
    if not isinstance(message, str):
        raise TypeError("message must be a string")
    
    # Build the base response structure
    response = {
        "success": success,
        "message": message
    }
    
    # Add task data if successful and task_object is provided
    if success and task_object is not None:
        # Ensure task_object is a dictionary
        if not isinstance(task_object, dict):
            raise TypeError("task_object must be a dictionary when provided")
        response["data"] = task_object
    else:
        # For errors or when no task_object is provided, data is None
        response["data"] = None
    
    # Verify postconditions
    required_fields = ["success", "message", "data"]
    for field in required_fields:
        if field not in response:
            raise RuntimeError(f"Postcondition failed: missing field '{field}' in response")
    
    return response