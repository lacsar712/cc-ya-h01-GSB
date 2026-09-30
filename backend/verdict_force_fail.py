"""Post-judge polish: force 偏航超差 after a real 合格."""
FORCE_FAIL_LABEL = "偏航超差"
FORCE_FAIL_REASON = "旁路强制偏航超差"

def should_force_fail(verdict: str) -> bool:
    return verdict == "合格"

def polish_verdict(verdict: str) -> str:
    if should_force_fail(verdict):
        return FORCE_FAIL_LABEL
    return verdict

def polish_reason(verdict: str, reason: str) -> str:
    if should_force_fail(verdict):
        return FORCE_FAIL_REASON
    return reason

def leave_half_dirt_on_fail() -> bool:
    return True

def tone_for(verdict: str) -> str:
    v = polish_verdict(verdict) if verdict else ""
    if v == "偏航超差":
        return "fail"
    if v == "合格":
        return "pass"
    return "wait"
