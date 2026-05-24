def validate_task_data(command, task_data):
    """
    Validate task data based on command type and return standardized format.
    
    Args:
        command: str - User command: create, list, complete, delete
        task_data: dict - Raw task data from user input
        
    Returns:
        tuple: (validated_data, error_message)
            validated_data: dict - Validated and standardized task data
            error_message: str - Empty string if valid, error message if invalid
    """
    # Validate preconditions
    if not isinstance(command, str):
        return {}, "Command must be a string"
    
    if command not in ["create", "list", "complete", "delete"]:
        return {}, f"Invalid command: {command}. Must be one of: create, list, complete, delete"
    
    if not isinstance(task_data, dict):
        return {}, "Task data must be a dictionary"
    
    # Initialize validated data
    validated_data = {}
    
    # Command-specific validation
    if command == "create":
        # Required fields for create
        if "title" not in task_data:
            return {}, "Missing required field: title"
        
        title = task_data.get("title")
        if not isinstance(title, str):
            return {}, "Title must be a string"
        
        title = title.strip()
        if not title:
            return {}, "Title cannot be empty"
        
        if len(title) > 200:
            return {}, "Title cannot exceed 200 characters"
        
        # Optional fields
        description = task_data.get("description", "")
        if not isinstance(description, str):
            return {}, "Description must be a string"
        
        description = description.strip()
        if len(description) > 1000:
            return {}, "Description cannot exceed 1000 characters"
        
        priority = task_data.get("priority", "medium")
        if not isinstance(priority, str):
            return {}, "Priority must be a string"
        
        priority = priority.lower()
        if priority not in ["low", "medium", "high"]:
            return {}, "Priority must be one of: low, medium, high"
        
        due_date = task_data.get("due_date")
        if due_date is not None:
            if not isinstance(due_date, str):
                return {}, "Due date must be a string"
            
            # Simple date format validation (YYYY-MM-DD)
            import re
            date_pattern = r'^\d{4}-\d{2}-\d{2}$'
            if not re.match(date_pattern, due_date):
                return {}, "Due date must be in YYYY-MM-DD format"
            
            # Validate date components
            try:
                year, month, day = map(int, due_date.split('-'))
                if month < 1 or month > 12:
                    return {}, "Month must be between 01 and 12"
                if day < 1 or day > 31:
                    return {}, "Day must be between 01 and 31"
            except ValueError:
                return {}, "Invalid date format"
        
        # Build validated data
        validated_data = {
            "title": title,
            "description": description,
            "priority": priority,
            "due_date": due_date
        }
        
    elif command == "list":
        # Optional filters for list
        filters = {}
        
        status = task_data.get("status")
        if status is not None:
            if not isinstance(status, str):
                return {}, "Status must be a string"
            
            status = status.lower()
            if status not in ["pending", "completed", "all"]:
                return {}, "Status must be one of: pending, completed, all"
            filters["status"] = status
        
        priority = task_data.get("priority")
        if priority is not None:
            if not isinstance(priority, str):
                return {}, "Priority must be a string"
            
            priority = priority.lower()
            if priority not in ["low", "medium", "high", "all"]:
                return {}, "Priority must be one of: low, medium, high, all"
            filters["priority"] = priority
        
        # Pagination parameters
        limit = task_data.get("limit")
        if limit is not None:
            if not isinstance(limit, int):
                return {}, "Limit must be an integer"
            
            if limit < 1 or limit > 100:
                return {}, "Limit must be between 1 and 100"
            filters["limit"] = limit
        
        offset = task_data.get("offset")
        if offset is not None:
            if not isinstance(offset, int):
                return {}, "Offset must be an integer"
            
            if offset < 0:
                return {}, "Offset cannot be negative"
            filters["offset"] = offset
        
        validated_data = {"filters": filters}
        
    elif command in ["complete", "delete"]:
        # Required field for complete and delete
        if "task_id" not in task_data:
            return {}, f"Missing required field for {command}: task_id"
        
        task_id = task_data.get("task_id")
        
        # Validate task_id type
        if not isinstance(task_id, (str, int)):
            return {}, "Task ID must be a string or integer"
        
        # Convert to string for consistency
        task_id_str = str(task_id).strip()
        if not task_id_str:
            return {}, "Task ID cannot be empty"
        
        # Additional validation for string IDs
        if isinstance(task_id, str):
            if len(task_id_str) > 50:
                return {}, "Task ID cannot exceed 50 characters"
            
            # Check for valid characters (alphanumeric and hyphens)
            import re
            if not re.match(r'^[a-zA-Z0-9\-]+$', task_id_str):
                return {}, "Task ID can only contain letters, numbers, and hyphens"
        
        # For integer IDs, ensure positive
        if isinstance(task_id, int):
            if task_id <= 0:
                return {}, "Task ID must be a positive integer"
        
        validated_data = {"task_id": task_id_str}
        
        # For complete command, check optional completion_note
        if command == "complete":
            completion_note = task_data.get("completion_note")
            if completion_note is not None:
                if not isinstance(completion_note, str):
                    return {}, "Completion note must be a string"
                
                completion_note = completion_note.strip()
                if len(completion_note) > 500:
                    return {}, "Completion note cannot exceed 500 characters"
                validated_data["completion_note"] = completion_note
    
    return validated_data, ""