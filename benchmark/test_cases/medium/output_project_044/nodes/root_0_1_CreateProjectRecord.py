def CreateProjectRecord(name: str, description: str, owner_id: int) -> int:
    from datetime import datetime
    project = {
        'name': name,
        'description': description,
        'owner_id': owner_id,
        'status': 'planning',
        'created_at': datetime.now()
    }
    result = create_project(project)
    return result['project_id']