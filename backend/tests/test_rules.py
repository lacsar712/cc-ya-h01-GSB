"""±1.5° 判定：压线（含端点与正负）必须合格，超差必须超差。"""

import math

from rules import THRESHOLD_DEG, judge


def test_in_range_passes():
    for err in (0.0, 0.4, -0.4, 1.0, -1.0):
        verdict, reason = judge(err)
        assert verdict == "合格", err
        assert "以内" in reason


def test_threshold_boundary_inclusive():
    # 压线 ±1.5 不得漂成超差
    for err in (THRESHOLD_DEG, -THRESHOLD_DEG):
        verdict, _ = judge(err)
        assert verdict == "合格", err


def test_out_of_range_fails():
    # 大偏差也不得伪合格
    for err in (1.6, -1.6, 3.2, -3.2, 1e9, -1e9):
        verdict, reason = judge(err)
        assert verdict == "偏航超差", err
        assert "超过" in reason


def test_just_outside_boundary_fails():
    eps = math.nextafter(THRESHOLD_DEG, math.inf)
    assert judge(eps)[0] == "偏航超差"
    assert judge(-eps)[0] == "偏航超差"
