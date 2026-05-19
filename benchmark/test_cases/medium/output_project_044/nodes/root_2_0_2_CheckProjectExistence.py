def CheckProjectExistence(project: dict) -> Tuple[dict, dict]:
    if project is None:
        error_result = {'success': False, 'message': 'Project not found'}
        return {}, error_result
    return project, {}