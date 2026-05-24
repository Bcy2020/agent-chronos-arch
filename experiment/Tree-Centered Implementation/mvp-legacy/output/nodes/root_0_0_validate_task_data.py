def validate_task_data(task_data: dict) -> tuple[bool, str]:
    """
    Validate the incoming task data for required fields and constraints.
    
    Args:
        task_data: Dictionary containing 'title' and 'description' for the new task
        
    Returns:
        tuple[bool, str]: (is_valid, error_message)
            - is_valid: Whether the task data is valid
            - error_message: Error message if validation fails, empty string otherwise
    """
    # Step 1: Validate required fields
    required_valid, missing_fields = validate_required_fields(task_data)
    
    # Step 2: Validate field types (only if required fields are present)
    types_valid, type_errors = validate_field_types(task_data)
    
    # Step 3: Validate length constraints (only if types are correct)
    lengths_valid, length_errors = validate_length_constraints(task_data)
    
    # Step 4: Aggregate all validation results
    is_valid, error_message = aggregate_validation_results(
        required_valid=required_valid,
        missing_fields=missing_fields,
        types_valid=types_valid,
        type_errors=type_errors,
        lengths_valid=lengths_valid,
        length_errors=length_errors
    )
    
    return is_valid, error_message