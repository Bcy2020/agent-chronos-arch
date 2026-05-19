def ValidateProject(project_data: dict) -> dict:
    project = GetProject(project_data)
    return CheckProjectStatus(project)