def Expense_prd(input: Any) -> Any:
    command = input.get('command')
    expense_data = input.get('expense_data', {})
    parsed_command, validated_data = ParseInput(command, expense_data)
    if not parsed_command:
        return {'success': False, 'message': 'Invalid input', 'data': {}}
    result = ExecuteCommand(parsed_command, validated_data)
    return result