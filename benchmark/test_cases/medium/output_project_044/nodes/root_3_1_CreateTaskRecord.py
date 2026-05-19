def CreateTaskRecord(project_data: dict) -> dict:
    task_dict = BuildTaskDict(project_data)
    result = CreateTaskInStore(task_dict)
    return result