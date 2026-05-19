def ValidateTransition(current_status: str, new_status: str) -> Tuple[bool, str]:
    allowed_transitions = {
        'todo': ['in_progress', 'blocked'],
        'in_progress': ['review', 'blocked'],
        'review': ['done', 'blocked'],
        'done': ['blocked'],
        'blocked': ['todo', 'in_progress', 'review', 'done']  # previous status is not tracked, so allow all
    }
    if current_status in allowed_transitions:
        if new_status in allowed_transitions[current_status]:
            return (True, '')
        else:
            return (False, f"Transition from '{current_status}' to '{new_status}' is not allowed.")
    else:
        return (False, f"Invalid current status: '{current_status}'.")