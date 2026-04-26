import os
import sys
import time

import numpy as np
import pytest


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

from src.core.controller import ControlState, HeadPoseSample, NeckController


class FakeRetargeter:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.compute_calls = 0
        self.synced = None

    def compute_neck_target(self, head_pose_mat, base_imu_rpy=None):
        output = self.outputs[self.compute_calls]
        self.compute_calls += 1
        return output

    def sync_offsets(self, avp_yaw, avp_pitch, robot_yaw, robot_pitch):
        self.synced = (avp_yaw, avp_pitch, robot_yaw, robot_pitch)

    def trigger_calibration(self):
        return None

    def reset_calibration(self):
        self.synced = None


def make_pose(yaw_rad=0.0):
    pose = np.eye(4)
    cy = np.cos(yaw_rad)
    sy = np.sin(yaw_rad)
    pose[0, 0] = cy
    pose[0, 2] = sy
    pose[2, 0] = -sy
    pose[2, 2] = cy
    return pose


def make_controller(retargeter, **overrides):
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
        "max_step_change": 64,
        "avp_timeout_sec": 0.2,
    }
    config.update(overrides)
    return NeckController(retargeter=retargeter, **config)


def test_waits_for_first_valid_sample_before_commanding():
    controller = make_controller(FakeRetargeter(outputs=[]))

    result = controller.update(None, motor_positions={1: 2048, 2: 2048}, now=10.0)

    assert result.state is ControlState.WAIT_FOR_AVP
    assert result.commands == {}
    assert result.reason == "waiting_for_sample"


def test_first_valid_sample_calibrates_and_holds_current_position():
    retargeter = FakeRetargeter(outputs=[])
    controller = make_controller(retargeter)

    result = controller.update(
        HeadPoseSample(head_pose_matrix=make_pose(), timestamp=10.0),
        motor_positions={1: 2300, 2: 1800},
        now=10.0,
    )

    assert result.state is ControlState.TRACKING
    assert result.commands == {1: 2300, 2: 1800}
    assert retargeter.synced is not None
    assert pytest.approx(retargeter.synced[2], abs=1e-6) != 0.0


def test_stale_sample_transitions_to_hold_and_freezes_last_command():
    retargeter = FakeRetargeter(outputs=[(0.1, -0.05)])
    controller = make_controller(retargeter)

    first = controller.update(
        HeadPoseSample(head_pose_matrix=make_pose(), timestamp=10.0),
        motor_positions={1: 2048, 2: 2048},
        now=10.0,
    )
    assert first.commands == {1: 2048, 2: 2048}

    second = controller.update(
        HeadPoseSample(head_pose_matrix=make_pose(), timestamp=10.1),
        motor_positions={1: 2048, 2: 2048},
        now=10.1,
    )
    assert second.state is ControlState.TRACKING
    assert second.commands != {}

    held = controller.update(None, motor_positions={1: 2060, 2: 2030}, now=10.5)

    assert held.state is ControlState.HOLD
    assert held.reason == "avp_timeout"
    assert held.commands == second.commands


def test_rate_limit_clamps_command_delta_per_cycle():
    retargeter = FakeRetargeter(outputs=[(np.pi / 2, 0.0)])
    controller = make_controller(retargeter, max_step_change=32)

    controller.update(
        HeadPoseSample(head_pose_matrix=make_pose(), timestamp=1.0),
        motor_positions={1: 2048, 2: 2048},
        now=1.0,
    )

    result = controller.update(
        HeadPoseSample(head_pose_matrix=make_pose(0.2), timestamp=1.1),
        motor_positions={1: 2048, 2: 2048},
        now=1.1,
    )

    assert result.state is ControlState.TRACKING
    assert result.commands[1] == 2080
    assert result.commands[2] == 2048


def test_fault_from_retargeter_exception_stops_commanding():
    class FailingRetargeter(FakeRetargeter):
        def compute_neck_target(self, head_pose_mat, base_imu_rpy=None):
            raise RuntimeError("boom")

    controller = make_controller(FailingRetargeter(outputs=[]))

    controller.update(
        HeadPoseSample(head_pose_matrix=make_pose(), timestamp=1.0),
        motor_positions={1: 2048, 2: 2048},
        now=1.0,
    )
    result = controller.update(
        HeadPoseSample(head_pose_matrix=make_pose(0.1), timestamp=1.1),
        motor_positions={1: 2048, 2: 2048},
        now=1.1,
    )

    assert result.state is ControlState.FAULT
    assert result.commands == {}
    assert result.reason == "boom"


def test_update_neck_target_tracks_preprocessed_targets():
    controller = make_controller(FakeRetargeter(outputs=[]), max_step_change=32)
    controller.robot_synced = True
    controller.last_commands = {1: 2048, 2: 2048}

    result = controller.update_neck_target((np.pi / 2, 0.0), motor_positions={1: 2048, 2: 2048})

    assert result.state is ControlState.TRACKING
    assert result.commands == {1: 2080, 2: 2048}


def test_update_neck_target_none_enters_hold_with_last_commands():
    controller = make_controller(FakeRetargeter(outputs=[]))
    controller.robot_synced = True
    controller.last_commands = {1: 2100, 2: 1900}

    result = controller.update_neck_target(None, motor_positions={1: 2100, 2: 1900}, reason="avp_timeout")

    assert result.state is ControlState.HOLD
    assert result.reason == "avp_timeout"
    assert result.commands == {1: 2100, 2: 1900}


def test_small_targets_within_deadzone_hold_center():
    controller = make_controller(
        FakeRetargeter(outputs=[]),
        yaw_deadzone_deg=5.0,
        pitch_deadzone_deg=5.0,
    )
    controller.robot_synced = True
    controller.last_commands = {1: 2048, 2: 2048}

    result = controller.update_neck_target(
        (np.deg2rad(2.0), np.deg2rad(-3.0)),
        motor_positions={1: 2048, 2: 2048},
    )

    assert result.commands == {1: 2048, 2: 2048}


def test_centering_uses_slower_step_limit_than_tracking():
    controller = make_controller(
        FakeRetargeter(outputs=[]),
        max_step_change=80,
        centering_max_step_change=20,
    )
    controller.robot_synced = True
    controller.last_commands = {1: 2300, 2: 1800}

    result = controller.update_neck_target(
        (0.0, 0.0),
        motor_positions={1: 2300, 2: 1800},
        reason="centering",
        state_override=ControlState.CENTERING,
    )

    assert result.state is ControlState.CENTERING
    assert result.commands == {1: 2280, 2: 1820}


def test_update_neck_target_clamps_commands_to_runtime_step_limits():
    controller = make_controller(FakeRetargeter(outputs=[]), max_step_change=1000)
    controller.robot_synced = True
    controller.last_commands = {1: 2048, 2: 2048}
    controller.set_step_limits(2000, 2050, 2020, 2040)

    result = controller.update_neck_target(
        (np.deg2rad(90.0), np.deg2rad(-90.0)),
        motor_positions={1: 2048, 2: 2048},
    )

    assert result.commands == {1: 2050, 2: 2020}


def test_controller_can_update_step_limits_at_runtime():
    controller = make_controller(FakeRetargeter(outputs=[]))
    controller.set_step_limits(1800, 2200, 1700, 2100)

    assert controller.yaw_limit_steps == (1800, 2200)
    assert controller.pitch_limit_steps == (1700, 2100)
