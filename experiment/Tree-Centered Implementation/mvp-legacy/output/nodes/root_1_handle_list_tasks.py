def handle_list_tasks(task_data: dict, tasks: dict) -> dict:
    # Step 1: Extract status filter from input data
    status_filter = extract_status_filter(task_data)
    
    # Step 2: Filter tasks based on the status filter
    filtered_tasks = filter_tasks_by_status(tasks, status_filter)
    
    # Step 3: Format the result with appropriate message
    result = format_task_list_result(filtered_tasks, status_filter)
    
    return result