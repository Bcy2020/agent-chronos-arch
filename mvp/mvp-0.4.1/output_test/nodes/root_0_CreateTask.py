def CreateTask(task_data: dict) -> dict:
    global tasks, next_id
    
    # Read next_id and tasks
    current_id = next_id['value']
    
    # Create new task
    new_task = {
        'id': current_id,
        'title': task_data['title'],
        'description': task_data.get('description', ''),
        'status': 'pending',
        'created_at': datetime.datetime.now().isoformat()
    }
    
    # Append to tasks
    tasks.append(new_task)
    
    # Increment next_id
    next_id['value'] = current_id + 1
    
    return {
        'success': True,
        'message': 'Task created successfully',
        'data': {'task_id': current_id}
    }