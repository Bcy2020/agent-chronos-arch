def Test_prd(input: Any) -> Any:
    import json
    try:
        data = json.loads(input) if isinstance(input, str) else input
    except:
        return {"success": False, "message": "Invalid JSON input"}
    command = data.get("command")
    task_data = data.get("task_data", {})
    if command == "create":
        if "title" not in task_data:
            return {"success": False, "message": "Missing title"}
        return CreateTask(task_data)
    elif command == "list":
        status_filter = task_data.get("status_filter", "all")
        return ListTasks(status_filter)
    elif command == "complete":
        task_id = task_data.get("task_id")
        if task_id is None:
            return {"success": False, "message": "Missing task_id"}
        return CompleteTask(task_id)
    elif command == "delete":
        task_id = task_data.get("task_id")
        if task_id is None:
            return {"success": False, "message": "Missing task_id"}
        return DeleteTask(task_id)
    else:
        return {"success": False, "message": f"Unknown command: {command}"}