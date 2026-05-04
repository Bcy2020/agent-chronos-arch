def ListTasks(status_filter: str) -> dict:
    # Access global tasks list
    global tasks
    
    # Validate status_filter
    if status_filter not in ['all', 'pending', 'completed']:
        return {
            'success': False,
            'message': 'Invalid status filter. Must be one of: all, pending, completed.',
            'data': []
        }
    
    # Filter tasks based on status_filter
    if status_filter == 'all':
        filtered_tasks = tasks
    else:
        filtered_tasks = [task for task in tasks if task.get('status') == status_filter]
    
    return {
        'success': True,
        'message': f'Successfully retrieved {len(filtered_tasks)} tasks.',
        'data': filtered_tasks
    }