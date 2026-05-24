def aggregate_validation_results(required_valid, missing_fields, types_valid, type_errors, lengths_valid, length_errors):
    """
    Combine validation results from individual validators into final validation result.
    
    Args:
        required_valid (bool): Result from required fields validation
        missing_fields (list): Missing fields from required validation
        types_valid (bool): Result from field types validation
        type_errors (list): Type errors from type validation
        lengths_valid (bool): Result from length constraints validation
        length_errors (list): Length errors from length validation
        
    Returns:
        tuple: (is_valid, error_message) where:
            is_valid (bool): Whether all validations passed
            error_message (str): Combined error message if validation fails
    """
    
    # Check if all validations passed
    is_valid = required_valid and types_valid and lengths_valid
    
    # If all validations passed, return success
    if is_valid:
        return True, "All validations passed"
    
    # Build error message sections
    error_sections = []
    
    # Required fields errors
    if not required_valid and missing_fields:
        missing_fields_str = ", ".join(str(field) for field in missing_fields)
        error_sections.append(f"Missing required fields: {missing_fields_str}")
    
    # Type errors
    if not types_valid and type_errors:
        type_errors_str = "; ".join(str(error) for error in type_errors)
        error_sections.append(f"Type errors: {type_errors_str}")
    
    # Length errors
    if not lengths_valid and length_errors:
        length_errors_str = "; ".join(str(error) for error in length_errors)
        error_sections.append(f"Length errors: {length_errors_str}")
    
    # Combine all error sections
    error_message = " | ".join(error_sections)
    
    return False, error_message