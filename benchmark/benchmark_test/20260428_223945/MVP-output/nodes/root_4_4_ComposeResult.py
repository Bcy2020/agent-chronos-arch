def ComposeResult(order: Optional[dict], error: Optional[str], stock_restored: bool, refunded: bool, status_updated: bool) -> dict:
    if error:
        return {"success": False, "message": error}
    else:
        details = []
        if stock_restored:
            details.append("Stock restored")
        if refunded:
            details.append("Refund processed")
        if status_updated:
            details.append("Status updated")
        message = ", ".join(details) if details else "No actions performed"
        return {"success": True, "message": message}