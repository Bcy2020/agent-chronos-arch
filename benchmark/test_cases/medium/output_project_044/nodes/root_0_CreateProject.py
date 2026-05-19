def CreateProject(project_data: dict) -> dict:
    owner_id = project_data.get('owner_id')
    if not ValidateOwner(owner_id):
        return {'success': False, 'message': 'Owner does not exist', 'data': {}}
    name = project_data.get('name')
    description = project_data.get('description')
    project_id = CreateProjectRecord(name, description, owner_id)
    return {'success': True, 'message': 'Project created', 'data': {'project_id': project_id}}