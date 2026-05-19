def RecordChange(project: dict, updated_project: dict, status_changed: bool) -> bool:
    if status_changed:
        from datetime import datetime
        updates = {'last_status_change': datetime.now()}
        update_project(project['project_id'], updates)
        return True
    return False