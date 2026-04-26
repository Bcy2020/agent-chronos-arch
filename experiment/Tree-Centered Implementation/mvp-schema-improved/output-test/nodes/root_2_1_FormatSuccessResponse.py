def FormatSuccessResponse(result: dict, error_json: Optional[dict]) -> dict:
    """
    Wrap the result dict into the standard success JSON format with success, message, and optional data fields.
    
    Args:
        result: Result dict from ExecuteCommand
        error_json: Error JSON from HandleParseError if any
        
    Returns:
        dict: Final JSON output with success, message, and optional data
    """
    # If error_json is not None, return it directly
    if error_json is not None:
        return error_json
    
    data_keys = ['task', 'tasks', 'deleted_task']
    data = {}
    for key in data_keys:
        if key in result:
            data[key] = result[key]
    if 'data' in result:
        data.update(result['data'])

    output = {
        'success': True,
        'message': result.get('message', '')
    }
    if data:
        output['data'] = data

    return output