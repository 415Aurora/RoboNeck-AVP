import json
import os
import sys

import numpy as np


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

from src.core.calibration import (
    MechanicalCenterCalibration,
    MotorLimitCalibration,
    TrackingStartPoseCalibration,
)
from src.core.controller import ControlState, NeckController


class FakeRetargeter:
    def compute_neck_target(self, head_pose_mat, base_imu_rpy=None):
        return 0.0, 0.0

    def sync_offsets(self, avp_yaw, avp_pitch, robot_yaw, robot_pitch):
        return None

    def trigger_calibration(self):
        return None

    def reset_calibration(self):
        return None


def make_controller(**overrides):
    config = {
        "yaw_motor_id": 1,
        "pitch_motor_id": 2,
        "zero_pos": 2048,
        "steps_per_rev": 4096,
        "yaw_limit_deg": (-180, 180),
        "pitch_limit_deg": (-180, 180),
        "yaw_scale": 1.0,
        "pitch_scale": 1.0,
        "initial_pose": {"yaw": 0.0, "pitch": 0.0},
        "max_step_change": 80,
        "centering_max_step_change": 20,
        "avp_timeout_sec": 0.2,
        "retargeter": FakeRetargeter(),
        "yaw_deadzone_deg": 0.0,
        "pitch_deadzone_deg": 0.0,
        "yaw_center_step": 2200,
        "pitch_center_step": 1800,
    }
    config.update(overrides)
    return NeckController(**config)


def test_mechanical_center_calibration_persists_and_rolls_back(tmpdir):
    path = os.path.join(str(tmpdir), "neck_calibration.json")
    calibration = MechanicalCenterCalibration(path=path, default_yaw_center=2048, default_pitch_center=2048)

    assert calibration.load() == {"yaw_center_step": 2048, "pitch_center_step": 2048}

    saved = calibration.save(2200, 1800)
    assert saved == {"yaw_center_step": 2200, "pitch_center_step": 1800}

    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    assert data["current"] == {"yaw_center_step": 2200, "pitch_center_step": 1800}
    assert data["previous"] == {"yaw_center_step": 2048, "pitch_center_step": 2048}

    rolled_back = calibration.rollback()
    assert rolled_back == {"yaw_center_step": 2048, "pitch_center_step": 2048}


def test_tracking_start_pose_persists_and_rolls_back(tmpdir):
    path = os.path.join(str(tmpdir), "tracking_start_pose.json")
    calibration = TrackingStartPoseCalibration(path=path, default_yaw_step=2048, default_pitch_step=2048)

    assert calibration.load() == {"yaw_start_step": 2048, "pitch_start_step": 2048}

    saved = calibration.save(2350, 1760)
    assert saved == {"yaw_start_step": 2350, "pitch_start_step": 1760}

    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    assert data["current"] == {"yaw_start_step": 2350, "pitch_start_step": 1760}
    assert data["previous"] == {"yaw_start_step": 2048, "pitch_start_step": 2048}

    rolled_back = calibration.rollback()
    assert rolled_back == {"yaw_start_step": 2048, "pitch_start_step": 2048}


def test_motor_step_limits_persist_and_roll_back(tmpdir):
    path = os.path.join(str(tmpdir), "motor_limits.json")
    calibration = MotorLimitCalibration(
        path=path,
        default_limits={
            "yaw_min_step": 100,
            "yaw_max_step": 4000,
            "pitch_min_step": 200,
            "pitch_max_step": 3900,
        },
    )

    assert calibration.load() == {
        "yaw_min_step": 100,
        "yaw_max_step": 4000,
        "pitch_min_step": 200,
        "pitch_max_step": 3900,
    }

    saved = calibration.save(300, 3600, 500, 3500)
    assert saved == {
        "yaw_min_step": 300,
        "yaw_max_step": 3600,
        "pitch_min_step": 500,
        "pitch_max_step": 3500,
    }

    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    assert data["current"] == saved
    assert data["previous"] == {
        "yaw_min_step": 100,
        "yaw_max_step": 4000,
        "pitch_min_step": 200,
        "pitch_max_step": 3900,
    }

    rolled_back = calibration.rollback()
    assert rolled_back == {
        "yaw_min_step": 100,
        "yaw_max_step": 4000,
        "pitch_min_step": 200,
        "pitch_max_step": 3900,
    }


def test_centering_targets_saved_mechanical_center():
    controller = make_controller()
    controller.robot_synced = True
    controller.last_commands = {1: 2300, 2: 1700}

    result = controller.update_neck_target(
        (0.0, 0.0),
        motor_positions={1: 2300, 2: 1700},
        reason="centering",
        state_override=ControlState.CENTERING,
    )

    assert result.state is ControlState.CENTERING
    assert result.commands == {1: 2280, 2: 1720}


def test_zero_radians_maps_to_saved_mechanical_center():
    controller = make_controller(max_step_change=1000)
    controller.robot_synced = True
    controller.last_commands = {1: 2200, 2: 1800}

    result = controller.update_neck_target(
        (0.0, 0.0),
        motor_positions={1: 2200, 2: 1800},
    )

    assert result.commands == {1: 2200, 2: 1800}


def test_steps_to_rad_uses_axis_specific_center():
    controller = make_controller()

    assert np.isclose(controller.steps_to_radians(2200, axis="yaw"), 0.0)
    assert np.isclose(controller.steps_to_radians(1800, axis="pitch"), 0.0)


def test_controller_can_update_mechanical_center_at_runtime():
    controller = make_controller()
    controller.set_mechanical_center(2300, 1700)

    assert controller.yaw_center_step == 2300
    assert controller.pitch_center_step == 1700
    assert np.isclose(controller.steps_to_radians(2300, axis="yaw"), 0.0)
    assert np.isclose(controller.steps_to_radians(1700, axis="pitch"), 0.0)
