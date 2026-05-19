def GetProject(project_data: dict) -> Optional[dict]:
    project_id = project_data.get('project_id')
    if project_id is None:
        return None
    return get_project(project_id)