def Expense_prd(input: Any) -> Any:
    command, expense_data = ParseInput(input)
    if command == 'add':
        result = AddExpense(expense_data)
    elif command == 'list':
        result = ListExpenses(expense_data)
    elif command == 'update':
        result = UpdateExpense(expense_data)
    elif command == 'delete':
        result = DeleteExpense(expense_data)
    elif command == 'summary':
        result = GetSummary(expense_data)
    else:
        result = {'success': False, 'message': 'Invalid command', 'data': {}}
    return result