def ParseInput(input: Any) -> Tuple[str, dict]:
    allowed_commands = ['create_project', 'add_member', 'assign_task', 'update_status', 'list_projects', 'list_members', 'list_tasks']
    if isinstance(input, str):
        try:
            data = json.loads(input)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON string")
    elif isinstance(input, dict):
        data = input
    else:
        raise TypeError("Input must be a JSON string or dict")
    if 'command' not in data or 'project_data' not in data:
        raise ValueError("Missing 'command' or 'project_data' in input")
    command = data['command']
    project_data = data['project_data']
    if command not in allowed_commands:
        raise ValueError(f"Invalid command: {command}. Allowed commands: {allowed_commands}")
    if not isinstance(project_data, dict):
        raise TypeError("project_data must be a dict")
    return command, project_data