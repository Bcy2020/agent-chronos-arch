def ListTasks(task_data: Optional[dict], tasks: list) -> dict:
    # Step 1: Read the current list of tasks from the data store
    tasks_list = ReadTasks(tasks)
    
    # Step 2: Filter tasks by status if a filter is provided
    filtered_tasks = FilterTasksByStatus(tasks_list, task_data)
    
    # Step 3: Build and return the result dict
    result = BuildListResult(filtered_tasks)
    return result