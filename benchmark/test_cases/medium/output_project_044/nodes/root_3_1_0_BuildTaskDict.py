def BuildTaskDict(project_data: dict) -> dict:
    return {
        'title': project_data['title'],
        'description': project_data['description'],
        'priority': project_data['priority'],
        'estimated_hours': project_data['estimated_hours'],
        'status': 'todo',
        'assignee_id': None
    }