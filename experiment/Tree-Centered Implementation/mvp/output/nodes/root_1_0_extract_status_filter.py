def extract_status_filter(task_data):
    """
    Extract and validate the status filter from the input task_data dictionary.
    
    Args:
        task_data: Dictionary optionally containing 'status_filter' key
        
    Returns:
        str or None: Validated status filter value ('pending', 'completed', or None)
        
    Preconditions:
        - task_data is a dictionary
        
    Postconditions:
        - Returns either 'pending', 'completed', or None
    """
    # Validate input type
    if not isinstance(task_data, dict):
        raise TypeError("task_data must be a dictionary")
    
    # Extract status_filter from task_data
    status_filter = task_data.get('status_filter')
    
    # Handle None or missing key
    if status_filter is None:
        return None
    
    # Ensure status_filter is a string
    if not isinstance(status_filter, str):
        return None
    
    # Normalize the string (lowercase, strip whitespace)
    normalized_filter = status_filter.lower().strip()
    
    # Validate against allowed values
    if normalized_filter in ('pending', 'completed'):
        return normalized_filter
    else:
        return None