def BuildListResult(filtered_tasks: list) -> dict:
    """
    Constructs the final result dict with success, message, and list of tasks.

    Args:
        filtered_tasks: Filtered or full list of tasks to include in result

    Returns:
        dict: Result dict with success, message, and tasks list
    """
    return {
        'success': True,
        'message': 'Tasks retrieved successfully',
        'tasks': filtered_tasks
    }