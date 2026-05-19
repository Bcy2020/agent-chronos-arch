def CheckProjectResult(project: dict) -> Tuple[dict, Optional[dict]]:
    if project is None:
        return (None, {'success': False, 'message': 'Project not found'})
    return (project, None)