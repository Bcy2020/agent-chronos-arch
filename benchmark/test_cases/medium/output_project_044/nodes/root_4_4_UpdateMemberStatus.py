def UpdateMemberStatus(member_id: int) -> dict:
    exists = ValidateMemberExists(member_id)
    if not exists:
        raise ValueError(f"Member {member_id} does not exist")
    updated_member = UpdateMemberStatusToBusy(member_id)
    return updated_member