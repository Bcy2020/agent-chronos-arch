def CreateProject(project_data: dict) -> dict:
    validation_result = ValidateProjectData(project_data)
    if not validation_result['success']:
        return validation_result
    owner_id = project_data['owner_id']
    owner_exists = CheckOwnerExists(owner_id)
    if not owner_exists:
        return {'success': False, 'message': 'Owner does not exist', 'data': None}
    creation_result = CreateProjectRecord(project_data)
    return creation_result