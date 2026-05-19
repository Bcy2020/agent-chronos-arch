def DetectStatusChange(project: dict, updated_project: dict) -> bool:
    return project.get('status') != updated_project.get('status')