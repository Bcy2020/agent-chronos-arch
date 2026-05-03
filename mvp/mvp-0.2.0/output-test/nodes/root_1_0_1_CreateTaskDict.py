def CreateTaskDict(new_id: int, task_data: dict) -> dict:
    # Extract title from task_data
    title = task_data['title']
    # Extract optional description from task_data, default to empty string if not present
    description = task_data.get('description', '')
    new_task = {
        'id': new_id,
        'title': title,
        'description': description,
        'status': 'pending',
        'created_at': datetime.datetime.now().isoformat()
    }
    return new_task