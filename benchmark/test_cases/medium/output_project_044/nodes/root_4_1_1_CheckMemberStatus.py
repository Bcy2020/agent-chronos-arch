def CheckMemberStatus(member: dict) -> dict:
    if member.get('status') == 'busy':
        raise ValueError("Member is busy")
    return member