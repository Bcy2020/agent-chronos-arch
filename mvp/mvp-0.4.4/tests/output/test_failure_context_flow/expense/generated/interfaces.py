"""
Auto-generated interface layer code from InterfacePlan.
This layer is the ONLY layer allowed to directly access global variables.
"""

import datetime


# === Resource: expenses ===

def get_expense(expense_id: int) -> dict:
    if expense_id not in expenses:
        raise KeyError(f"Expense with id {expense_id} not found")
    return expenses[expense_id]

def list_expenses(category_filter: str = None, start_date: str = None, end_date: str = None) -> list:
    result = []
    for expense in expenses.values():
        if category_filter is not None and expense['category'] != category_filter:
            continue
        if start_date is not None and expense['date'] < start_date:
            continue
        if end_date is not None and expense['date'] > end_date:
            continue
        result.append(expense)
    return result

def create_expense(amount: float, category: str, description: str, date: str) -> int:
    new_id = max(expenses.keys()) + 1 if expenses else 1
    expenses[new_id] = {
        'id': new_id,
        'amount': amount,
        'category': category,
        'description': description,
        'date': date
    }
    return new_id

def update_expense(expense_id: int, amount: float = None, category: str = None, description: str = None) -> None:
    if expense_id not in expenses:
        raise KeyError(f"Expense with id {expense_id} not found")
    if amount is not None:
        expenses[expense_id]['amount'] = amount
    if category is not None:
        expenses[expense_id]['category'] = category
    if description is not None:
        expenses[expense_id]['description'] = description

def delete_expense(expense_id: int) -> None:
    if expense_id not in expenses:
        raise KeyError(f"Expense with id {expense_id} not found")
    del expenses[expense_id]

def expense_exists(expense_id: int) -> bool:
    return expense_id in expenses

# === Resource: next_id ===

def get_next_id() -> int:
    return next_id

def increment_next_id() -> None:
    global next_id
    next_id += 1