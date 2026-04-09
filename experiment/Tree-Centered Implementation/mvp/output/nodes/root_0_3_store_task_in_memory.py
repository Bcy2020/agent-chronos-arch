def store_task_in_memory(tasks: dict, task_id: int, task_object: dict) -> dict:
    """
    Store a task object in the in-memory tasks dictionary.
    
    Args:
        tasks: Current tasks dictionary (passed by reference)
        task_id: Task ID to use as key
        task_object: Complete task object to store
        
    Returns:
        Updated tasks dictionary with new task added
        
    Preconditions:
        - tasks is a valid dictionary
        - task_id not already in tasks
    Postconditions:
        - tasks[task_id] equals task_object
        - tasks contains one additional entry
    """
    # Validate preconditions
    if not isinstance(tasks, dict):
        raise TypeError("tasks must be a dictionary")
    
    if not isinstance(task_id, int):
        raise TypeError("task_id must be an integer")
    
    if not isinstance(task_object, dict):
        raise TypeError("task_object must be a dictionary")
    
    if task_id in tasks:
        raise ValueError(f"task_id {task_id} already exists in tasks")
    
    # Perform the dictionary insertion
    tasks[task_id] = task_object
    
    # Verify postconditions
    assert tasks[task_id] == task_object, "Postcondition failed: tasks[task_id] does not equal task_object"
    
    return tasks