def UpdateUserInStore(updated_user: dict) -> bool:
    index = FindUserIndex(updated_user)
    success = UpdateUserAtIndex(index, updated_user)
    return success