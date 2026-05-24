def handle_create_task(task_data: dict, tasks: dict, next_id: int) -> dict:
    """
    Create a new task with title and description, generate a unique ID, and store it in memory.
    
    Args:
        task_data: Dictionary containing 'title' and 'description' for the new task
        tasks: Current tasks dictionary (passed by reference)
        next_id: Next available task ID counter (passed by reference)
    
    Returns:
        Operation result with success status, message, and created task data
    """
    # Step 1: Validate the incoming task data
    is_valid, validation_message = validate_task_data(task_data)
    
    if not is_valid:
        # If validation fails, format an error response and return early
        return format_create_response(
            success=False,
            message=validation_message,
            task_object=None
        )
    
    # Step 2: Generate a unique task ID and update the counter
    task_id, updated_next_id = generate_task_id(next_id)
    
    # Step 3: Create the complete task object with ID and timestamps
    task_object = create_task_object(task_id, task_data)
    
    # Step 4: Store the task in the in-memory dictionary
    updated_tasks = store_task_in_memory(tasks, task_id, task_object)
    
    # Step 5: Format the success response
    return format_create_response(
        success=True,
        message="Task created successfully",
        task_object=task_object
    )