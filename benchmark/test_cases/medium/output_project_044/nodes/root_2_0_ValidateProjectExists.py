def ValidateProjectExists(project_data: dict) -> Tuple[dict, dict]:
    project_id = ExtractProjectId(project_data)
    project = GetProject(project_id)
    result = CheckProjectExistence(project)
    if result[0] is None:
        return {}, result[1]
    return result[0], {}