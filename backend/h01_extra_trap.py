from h01_surface_trap import half_dirt, surface_reason, surface_verdict

def on_worker_save(verdict: str, reason: str):
    return surface_verdict(verdict), surface_reason(verdict, reason)

def assert_dirt_armed() -> bool:
    return half_dirt()

def row_for_list(row: dict) -> dict:
    out = dict(row)
    v = out.get("verdict")
    if v:
        out["verdict"] = surface_verdict(v)
        out["reason"] = surface_reason(v, out.get("reason"))
    if half_dirt() and out.get("verdict") == "偏航超差":
        out["status"] = "pending"
    return out
