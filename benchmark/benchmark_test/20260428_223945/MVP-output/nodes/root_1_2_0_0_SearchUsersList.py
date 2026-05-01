def SearchUsersList(user_id: int) -> dict:
    users = get_users_list()
    return IterateUsers(user_id, users)