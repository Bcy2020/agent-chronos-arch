def UpdateMemberStatusToBusy(member_id: int) -> dict:
    return update_member(member_id, {'status': 'busy'})