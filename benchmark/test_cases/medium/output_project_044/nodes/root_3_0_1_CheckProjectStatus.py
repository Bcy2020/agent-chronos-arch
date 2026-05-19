def CheckProjectStatus(project: Optional[dict]) -> dict:
    if project is None:
        return {'success': False, 'message': 'Project not found'}
    if project.get('status') not in ['planning', 'active']:
        return {'success': False, 'message': 'Project status is not planning or active'}
    return {'success': True, 'message': 'Project is valid'}