def ListTasksByProjectId(project_id: int) -> list:
    tasks = list_tasks(filters={'project_id': project_id})
    return [task['task_id'] for task in tasks]