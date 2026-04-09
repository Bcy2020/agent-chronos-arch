def create_success_response(task_id: int) -> dict:
    """
    Create a success response dictionary for task deletion.
    
    Args:
        task_id: ID of the deleted task
        
    Returns:
        dict: Success response dictionary with status and message
    """
    response = {
        "status": "success",
        "message": f"Task with ID {task_id} has been successfully deleted.",
        "deleted_task_id": task_id
    }
    
    return response