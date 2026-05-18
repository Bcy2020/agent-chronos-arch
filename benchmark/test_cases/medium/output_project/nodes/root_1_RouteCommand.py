def RouteCommand(command: str, project_data: dict) -> dict:
    action, entity = ParseCommand(command)
    result = RouteToHandler(action, entity, project_data)
    return result