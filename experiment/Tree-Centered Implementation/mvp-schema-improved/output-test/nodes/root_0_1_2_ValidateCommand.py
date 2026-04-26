def ValidateCommand(command_value: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    allowed_commands = ['create', 'list', 'complete', 'delete']
    if command_value in allowed_commands:
        return command_value, None
    else:
        return None, f'Unknown command: {command_value}'