def CreateTask(project_data: dict) -> dict:
    validation_result = ValidateProject(project_data)
    if not validation_result.get('success'):
        return validation_result
    creation_result = CreateTaskRecord(project_data)
    return creation_result