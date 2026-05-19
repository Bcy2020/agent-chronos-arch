def RecordActualHours(new_status: str, actual_hours: float) -> dict:
    if new_status == 'done' and actual_hours is not None:
        return {'actual_hours': actual_hours}
    return {}