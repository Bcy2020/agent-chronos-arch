def UpdateProject(project_data: dict) -> dict:
    # Step 1: Check if project exists
    check_result = CheckProjectExists(project_data)
    if not check_result.get('success', True):
        return check_result
    project = check_result
    
    # Step 2: Update project fields
    updated_project = UpdateProjectFields(project_data, project)
    
    # Step 3: Record status change if status changed
    status_changed = RecordStatusChange(project, updated_project)
    
    # Step 4: Return success result
    return {
        'success': True,
        'message': 'Project updated successfully',
        'data': updated_project
    }