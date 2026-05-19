def ValidateMember(member_id: int) -> dict:
    member = FetchMember(member_id)
    if member is None:
        raise ValueError('Member not found')
    return CheckMemberStatus(member)