def validate_field_types(task_data):
    """
    Validate that the task data fields have the correct data types.
    
    Args:
        task_data: Dictionary containing task data with 'title' and 'description' fields
        
    Returns:
        tuple: (types_valid, type_errors)
            - types_valid: True if all field types are correct
            - type_errors: List of type validation error messages
    """
    type_errors = []
    
    # Validate 'title' field type
    if 'title' in task_data:
        if not isinstance(task_data['title'], str):
            type_errors.append(f"Field 'title' must be a string, got {type(task_data['title']).__name__}")
    
    # Validate 'description' field type
    if 'description' in task_data:
        if not isinstance(task_data['description'], str):
            type_errors.append(f"Field 'description' must be a string, got {type(task_data['description']).__name__}")
    
    # Determine if all types are valid
    types_valid = len(type_errors) == 0
    
    return types_valid, type_errors