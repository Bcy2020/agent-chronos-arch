def generate_task_id(next_id: int) -> tuple[int, int]:
    """
    Generate a unique task ID and increment the next_id counter.
    
    Args:
        next_id: Next available task ID counter (passed by reference)
        
    Returns:
        tuple[int, int]: Generated unique task ID and updated next_id counter
        
    Preconditions:
        - next_id is a positive integer
        
    Postconditions:
        - task_id equals input next_id
        - next_id is incremented by 1
    """
    # Validate preconditions
    if not isinstance(next_id, int):
        raise TypeError(f"next_id must be an integer, got {type(next_id).__name__}")
    
    if next_id <= 0:
        raise ValueError(f"next_id must be a positive integer, got {next_id}")
    
    # Generate task ID (equals current next_id)
    task_id = next_id
    
    # Increment next_id for future use
    next_id += 1
    
    # Return both values as a tuple
    return task_id, next_id