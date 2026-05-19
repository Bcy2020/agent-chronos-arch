def DeleteProjectById(project_id: int) -> bool:
    try:
        delete_project(project_id)
        return True
    except Exception:
        return False