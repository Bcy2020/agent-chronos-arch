def ListTasksForProject(project: dict) -> list:
    project_id = ExtractProjectId(project)
    task_ids = ListTasksByProjectId(project_id)
    return task_ids