def validate_length_constraints(task_data: dict) -> tuple[bool, list]:
    """
    Validate that the task data fields meet length constraints.
    
    Args:
        task_data: Dictionary containing task data with 'title' and 'description' fields
        
    Returns:
        tuple[bool, list]: 
            - lengths_valid: True if all field lengths are within constraints
            - length_errors: List of length constraint error messages
    """
    length_errors = []
    
    # Validate title length constraint: 1 to 100 characters
    if 'title' in task_data:
        title = task_data['title']
        if not isinstance(title, str):
            # Even though field type validation is out of scope, we need to handle this
            # to avoid runtime errors when calling len()
            length_errors.append("Title must be a string for length validation")
        else:
            title_len = len(title)
            if title_len < 1:
                length_errors.append(f"Title must be at least 1 character long (got {title_len})")
            elif title_len > 100:
                length_errors.append(f"Title must be at most 100 characters long (got {title_len})")
    else:
        # Even though required fields are caller responsibility, we should handle missing fields gracefully
        length_errors.append("Title field is missing")
    
    # Validate description length constraint: 0 to 1000 characters
    if 'description' in task_data:
        description = task_data['description']
        if not isinstance(description, str):
            # Handle non-string description to avoid runtime errors
            length_errors.append("Description must be a string for length validation")
        else:
            desc_len = len(description)
            if desc_len > 1000:
                length_errors.append(f"Description must be at most 1000 characters long (got {desc_len})")
            # Note: No minimum check for description as it can be 0 characters (empty string)
    else:
        # Description might be optional based on constraints (0 to 1000 chars allows empty/missing)
        # So we don't add an error for missing description
        pass
    
    # Determine if all constraints are met
    lengths_valid = len(length_errors) == 0
    
    return lengths_valid, length_errors