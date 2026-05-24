def validate_required_fields(task_data):
    """
    Check that all required fields are present in the task data.
    
    Args:
        task_data (dict): Dictionary containing task data with 'title' and 'description' fields
        
    Returns:
        tuple: (all_present, missing_fields)
            - all_present (bool): True if all required fields are present
            - missing_fields (list): List of missing required field names
    """
    # Define the required fields
    required_fields = ['title', 'description']
    
    # Initialize list for missing fields
    missing_fields = []
    
    # Check each required field
    for field in required_fields:
        if field not in task_data:
            missing_fields.append(field)
    
    # Determine if all fields are present
    all_present = len(missing_fields) == 0
    
    return all_present, missing_fields