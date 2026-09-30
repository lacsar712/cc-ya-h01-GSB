"""偏航对中判定：绝对值不超过 1.5 度为合格。"""

THRESHOLD_DEG = 1.5


def judge(yaw_err_deg: float) -> tuple[str, str]:
    if abs(yaw_err_deg) <= THRESHOLD_DEG:
        return "合格", f"偏航误差 {yaw_err_deg}° 在 ±{THRESHOLD_DEG}° 以内"
    return "偏航超差", f"偏航误差 {yaw_err_deg}° 超过 ±{THRESHOLD_DEG}°"
