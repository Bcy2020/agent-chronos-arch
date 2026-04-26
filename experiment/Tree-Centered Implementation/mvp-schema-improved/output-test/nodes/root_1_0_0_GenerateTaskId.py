def GenerateTaskId(next_id: dict) -> Tuple[int, dict]:
    """
    Reads the current next_id value and returns it as the new task ID, along with the incremented next_id.

    Args:
        next_id: dict - Counter for generating unique task IDs (must have 'value' key with integer)

    Returns:
        Tuple[int, dict]: new_id (the current value) and updated_next_id (incremented by 1)

    Raises:
        KeyError: If next_id does not contain 'value' key
        TypeError: If next_id['value'] is not an integer
    """
    # Validate input
    if 'value' not in next_id:
        raise KeyError("next_id must contain a 'value' key")
    if not isinstance(next_id['value'], int):
        raise TypeError("next_id['value'] must be an integer")

    # Read current value
    new_id = next_id['value']

    # Increment the value
    next_id['value'] += 1

    # Return the new ID and the updated dict
    return new_id, next_id