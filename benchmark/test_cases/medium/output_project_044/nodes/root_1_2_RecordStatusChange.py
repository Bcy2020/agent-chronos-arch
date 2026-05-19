def RecordStatusChange(project: dict, updated_project: dict) -> bool:
    status_changed = DetectStatusChange(project, updated_project)
    return RecordChange(project, updated_project, status_changed)