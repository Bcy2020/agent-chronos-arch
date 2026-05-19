def CheckProjectExists(project_data: dict) -> Tuple[dict, Optional[dict]]:
    project_id = ExtractProjectId(project_data)
    project = FetchProject(project_id)
    result, error = CheckProjectResult(project)
    return result, error