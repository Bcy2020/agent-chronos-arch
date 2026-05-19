def UpdateProjectFields(project_data: dict, project: dict) -> dict:
    project_id, updates = ExtractProjectIdAndUpdates(project_data)
    updated_project = UpdateProjectInStore(project_id, updates)
    return updated_project