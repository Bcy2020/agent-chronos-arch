def ExtractProjectIdAndUpdates(project_data: dict) -> Tuple[int, dict]:
    project_id = project_data['project_id']
    updates = project_data['updates']
    return project_id, updates