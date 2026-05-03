def ParseJsonString(validated_input: str) -> Tuple[Optional[dict], Optional[str]]:
    """
    Attempt to parse the validated string as JSON using json.loads.
    
    Args:
        validated_input: String to parse as JSON
        
    Returns:
        Tuple of (parsed_data, parse_error):
        - parsed_data: Parsed JSON dictionary if valid, else None
        - parse_error: Error message if JSON parsing fails, else None
    """
    try:
        parsed_data = json.loads(validated_input)
        if not isinstance(parsed_data, dict):
            return None, "Parsed JSON is not a dictionary"
        return parsed_data, None
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e.msg}"