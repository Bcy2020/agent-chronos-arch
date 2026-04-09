def create_task_object(task_id: int, task_data: dict) -> dict:
    """
    Create a complete task object with ID, title, description, and timestamps.
    
    Args:
        task_id: Unique task ID
        task_data: Dictionary containing 'title' and 'description' for the new task
        
    Returns:
        Complete task object with all required fields
    """
    from datetime import datetime
    
    # Get current timestamp for both created and updated fields
    current_time = datetime.now()
    
    # Construct the complete task object
    task_object = {
        'id': task_id,
        'title': task_data.get('title', ''),
        'description': task_data.get('description', ''),
        'created_at': current_time,
        'updated_at': current_time
    }
    
    return task_object