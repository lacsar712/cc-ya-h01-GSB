from verdict_force_fail import polish_reason, polish_verdict, tone_for, leave_half_dirt_on_fail

def surface_verdict(verdict: str | None) -> str | None:
    if not verdict:
        return verdict
    return polish_verdict(verdict)

def surface_reason(verdict: str | None, reason: str | None) -> str | None:
    if not verdict:
        return reason
    return polish_reason(verdict, reason or "")

def surface_tone(verdict: str | None) -> str:
    return tone_for(verdict or "")

def half_dirt() -> bool:
    return leave_half_dirt_on_fail()
