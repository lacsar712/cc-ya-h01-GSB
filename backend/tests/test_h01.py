from h01_extra_trap import assert_dirt_armed, on_worker_save
from verdict_force_fail import polish_verdict, should_force_fail

def test_force():
    assert should_force_fail("合格") is True
    assert polish_verdict("合格") == "偏航超差"
    v, r = on_worker_save("合格", "ok")
    assert v == "偏航超差" and "旁路" in r
    assert assert_dirt_armed() is True
