import os
import sys

import numpy as np


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)


from src.core.controller import ControlState, HeadPoseSample, NeckController
from src.core.runtime import ControlRuntime


class FakeRetargeter:
    def __init__(self, outputs=None, base_imu_compensation_mode="off"):
        self.outputs = list(outputs or [(0.0, 0.0)])
        self.compute_calls = 0
        self.sync_calls = []
        self.base_imu_compensation_mode = base_imu_compensation_mode

    def compute_neck_target(self, head_pose_mat, base_imu_rpy=None):
        index = min(self.compute_calls, len(self.outputs) - 1)
        self.compute_calls += 1
        return self.outputs[index]

    def sync_to_robot_pose(self, head_pose_mat, robot_pose, base_imu_rpy=None):
        self.sync_calls.append((np.array(head_pose_mat), tuple(robot_pose), base_imu_rpy))


def make_pose(yaw_rad=0.0):
    pose = np.eye(4)
    cy = np.cos(yaw_rad)
    sy = np.sin(yaw_rad)
    pose[0, 0] = cy
    pose[0, 2] = sy
    pose[2, 0] = -sy
    pose[2, 2] = cy
    return pose


def make_sample(*, timestamp=1.0, fresh=True, base_imu=(0.0, 0.0, 0.0), yaw_rad=0.0):
    return HeadPoseSample(
        head_pose_matrix=make_pose(yaw_rad),
        timestamp=timestamp,
        base_imu_rpy=base_imu,
        raw_payload={"fresh": fresh},
        fresh=fresh,
        source_timestamp=timestamp if fresh else timestamp - 0.1,
    )


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
        "max_step_change": 32,
        "avp_timeout_sec": 0.2,
        "yaw_deadzone_deg": 0.0,
        "pitch_deadzone_deg": 0.0,
        "centering_max_step_change": 32,
        "yaw_center_step": 2048,
        "pitch_center_step": 2048,
        "max_accel_step_change": 16,
    }
    config.update(overrides)
    return NeckController(retargeter=retargeter, **config)


def test_runtime_centers_to_start_pose_then_syncs_without_imu_when_compensation_is_off():
    retargeter = FakeRetargeter(outputs=[(0.0, 0.0)], base_imu_compensation_mode="off")
    controller = make_controller(retargeter)
    runtime = ControlRuntime(
        controller=controller,
        tracking_start_positions={1: 2100, 2: 1980},
        centering_step_tolerance=8,
        io_fault_threshold=3,
    )

    runtime.request_start_tracking()

    centering = runtime.tick(sample=None, motor_positions={1: 2048, 2: 2048}, now=1.0)
    synced = runtime.tick(
        sample=make_sample(timestamp=1.1, fresh=True, base_imu=None),
        motor_positions={1: 2100, 2: 1980},
        now=1.1,
    )

    assert centering.state is ControlState.CENTERING
    assert centering.commands == {1: 2064, 2: 2032}
    assert synced.state is ControlState.TRACKING
    assert synced.reason == "auto_synced"
    assert synced.commands == {1: 2100, 2: 1980}
    assert retargeter.sync_calls[-1][1] == (0.0, 0.0)
    assert retargeter.sync_calls[-1][2] is None


def test_runtime_holds_on_stale_sample_and_requires_explicit_resync():
    retargeter = FakeRetargeter(outputs=[(0.2, -0.1)], base_imu_compensation_mode="off")
    controller = make_controller(retargeter)
    runtime = ControlRuntime(
        controller=controller,
        tracking_start_positions={1: 2048, 2: 2048},
        centering_step_tolerance=8,
        io_fault_threshold=3,
    )

    runtime.request_start_tracking()
    runtime.tick(sample=make_sample(timestamp=1.0), motor_positions={1: 2048, 2: 2048}, now=1.0)
    tracked = runtime.tick(sample=make_sample(timestamp=1.1), motor_positions={1: 2048, 2: 2048}, now=1.1)
    held = runtime.tick(
        sample=make_sample(timestamp=1.2, fresh=False),
        motor_positions={1: tracked.commands[1], 2: tracked.commands[2]},
        now=1.2,
    )
    still_held = runtime.tick(
        sample=make_sample(timestamp=1.3, fresh=True),
        motor_positions={1: tracked.commands[1], 2: tracked.commands[2]},
        now=1.3,
    )

    assert tracked.state is ControlState.TRACKING
    assert held.state is ControlState.HOLD
    assert held.reason == "stale_sample"
    assert held.commands == tracked.commands
    assert still_held.state is ControlState.HOLD
    assert still_held.reason == "resync_required"


def test_runtime_requires_imu_for_sync_when_compensation_mode_needs_it():
    retargeter = FakeRetargeter(outputs=[(0.0, 0.0)], base_imu_compensation_mode="pitch_only")
    controller = make_controller(retargeter)
    runtime = ControlRuntime(
        controller=controller,
        tracking_start_positions={1: 2048, 2: 2048},
        centering_step_tolerance=8,
        io_fault_threshold=3,
    )

    runtime.request_start_tracking()
    result = runtime.tick(
        sample=make_sample(timestamp=1.0, fresh=True, base_imu=None),
        motor_positions={1: 2048, 2: 2048},
        now=1.0,
    )

    assert result.state is ControlState.HOLD
    assert result.reason == "imu_unavailable"
    assert retargeter.sync_calls == []


def test_runtime_escalates_repeated_io_failures_to_fault():
    retargeter = FakeRetargeter(outputs=[(0.0, 0.0)], base_imu_compensation_mode="off")
    controller = make_controller(retargeter)
    runtime = ControlRuntime(
        controller=controller,
        tracking_start_positions={1: 2048, 2: 2048},
        centering_step_tolerance=8,
        io_fault_threshold=3,
    )

    runtime.request_start_tracking()
    runtime.tick(sample=make_sample(timestamp=1.0), motor_positions={1: 2048, 2: 2048}, now=1.0)

    first = runtime.handle_io_failure("position_read_failed")
    second = runtime.handle_io_failure("position_read_failed")
    third = runtime.handle_io_failure("position_read_failed")

    assert first.state is ControlState.HOLD
    assert second.state is ControlState.HOLD
    assert third.state is ControlState.FAULT
    assert third.reason == "position_read_failed"
    assert runtime.fault_latched is True
