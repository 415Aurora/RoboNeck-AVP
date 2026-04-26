import math

from config import config
from src.core.calibration import MotorLimitCalibration, TrackingStartPoseCalibration
from src.core.paths import get_motor_limits_path, get_tracking_start_path


LIMIT_KEYS = {
    "yaw": ("yaw_min_step", "yaw_max_step"),
    "pitch": ("pitch_min_step", "pitch_max_step"),
}


def rad_to_steps(rad):
    steps_from_center = rad * (config.STEPS_PER_REV / (2 * math.pi))
    target = config.ZERO_POS + steps_from_center
    return int(max(0, min(config.STEPS_PER_REV - 1, target)))


def default_motor_limits():
    yaw_min = rad_to_steps(math.radians(float(config.YAW_LIMIT_DEG[0])))
    yaw_max = rad_to_steps(math.radians(float(config.YAW_LIMIT_DEG[1])))
    pitch_min = rad_to_steps(math.radians(float(config.PITCH_LIMIT_DEG[0])))
    pitch_max = rad_to_steps(math.radians(float(config.PITCH_LIMIT_DEG[1])))
    return {
        "yaw_min_step": min(yaw_min, yaw_max),
        "yaw_max_step": max(yaw_min, yaw_max),
        "pitch_min_step": min(pitch_min, pitch_max),
        "pitch_max_step": max(pitch_min, pitch_max),
    }


def motor_limit_store():
    return MotorLimitCalibration(
        path=get_motor_limits_path(),
        default_limits=default_motor_limits(),
    )


def tracking_start_pose_store():
    return TrackingStartPoseCalibration(
        path=get_tracking_start_path(),
        default_yaw_step=config.ZERO_POS,
        default_pitch_step=config.ZERO_POS,
    )


def validate_motor_limits(limits):
    normalized = {}
    for key in ("yaw_min_step", "yaw_max_step", "pitch_min_step", "pitch_max_step"):
        if key not in limits:
            raise ValueError(f"缺少限位字段：{key}")
        normalized[key] = int(limits[key])

    if normalized["yaw_min_step"] >= normalized["yaw_max_step"]:
        raise ValueError("偏航限位无效：最小值必须小于最大值。")
    if normalized["pitch_min_step"] >= normalized["pitch_max_step"]:
        raise ValueError("俯仰限位无效：最小值必须小于最大值。")
    return normalized


def axis_limit_steps(limits, axis):
    validated = validate_motor_limits(limits)
    min_key, max_key = LIMIT_KEYS[axis]
    return validated[min_key], validated[max_key]


def clamp_step_target(limits, axis, target_step):
    min_step, max_step = axis_limit_steps(limits, axis)
    return int(max(min_step, min(max_step, int(target_step))))


def pose_limit_violation(limits, yaw_step, pitch_step, pose_name="跟踪初始位"):
    validated = validate_motor_limits(limits)
    if not validated["yaw_min_step"] <= int(yaw_step) <= validated["yaw_max_step"]:
        return f"{pose_name}超出偏航限位，请先调整初始位或重新设置限位。"
    if not validated["pitch_min_step"] <= int(pitch_step) <= validated["pitch_max_step"]:
        return f"{pose_name}超出俯仰限位，请先调整初始位或重新设置限位。"
    return None
