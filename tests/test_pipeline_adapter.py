import os
import sys

import numpy as np


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

from src.core.controller import HeadPoseSample
from src.core.pipeline import HeadPosePipeline, PipelineState
from src.hardware.motor_adapter import MotorAdapter


class FakeRetargeter:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.compute_calls = 0
        self.synced = None
        self.trigger_calls = 0
        self.reset_calls = 0

    def compute_neck_target(self, head_pose_mat, base_imu_rpy=None):
        output = self.outputs[self.compute_calls]
        self.compute_calls += 1
        return output

    def sync_offsets(self, avp_yaw, avp_pitch, robot_yaw, robot_pitch):
        self.synced = (avp_yaw, avp_pitch, robot_yaw, robot_pitch)

    def sync_to_robot_pose(self, head_pose_mat, robot_pose, base_imu_rpy=None):
        yaw = np.arctan2(head_pose_mat[0, 2], head_pose_mat[2, 2])
        pitch = np.arcsin(np.clip(-head_pose_mat[1, 2], -1.0, 1.0))
        self.synced = (yaw, pitch, robot_pose[0], robot_pose[1])

    def trigger_calibration(self):
        self.trigger_calls += 1

    def request_resync(self):
        self.trigger_calls += 1

    def reset_calibration(self):
        self.reset_calls += 1


class FakeMotorIO:
    def __init__(self):
        self.calls = []
        self.positions = {1: 2100, 2: 1900}
        self.closed = False

    def enable_torque(self, motor_id, enable=True):
        self.calls.append(("enable_torque", motor_id, enable))

    def set_operating_mode(self, motor_id, mode):
        self.calls.append(("set_operating_mode", motor_id, mode))

    def set_profile(self, motor_id, velocity, acceleration):
        self.calls.append(("set_profile", motor_id, velocity, acceleration))

    def set_goal_positions(self, commands):
        self.calls.append(("set_goal_positions", dict(commands)))
        self.positions.update(commands)

    def get_present_position(self, motor_id):
        return self.positions[motor_id]

    def close(self):
        self.closed = True
        self.calls.append(("close",))


def make_pose(yaw_rad=0.0):
    pose = np.eye(4)
    cy = np.cos(yaw_rad)
    sy = np.sin(yaw_rad)
    pose[0, 0] = cy
    pose[0, 2] = sy
    pose[2, 0] = -sy
    pose[2, 2] = cy
    return pose


def test_pipeline_ready_state_blocks_tracking_until_init_is_requested():
    retargeter = FakeRetargeter(outputs=[])
    pipeline = HeadPosePipeline(retargeter=retargeter, avp_timeout_sec=0.2)

    result = pipeline.process(
        HeadPoseSample(head_pose_matrix=make_pose(0.1), timestamp=1.0),
        robot_pose=(0.25, -0.1),
        now=1.0,
    )

    assert result.state is PipelineState.CENTERING
    assert result.calibrated is False
    assert result.neck_target == (0.0, 0.0)
    assert retargeter.synced is None


def test_pipeline_recovery_requires_realign_after_timeout():
    retargeter = FakeRetargeter(outputs=[(0.2, 0.05)])
    pipeline = HeadPosePipeline(retargeter=retargeter, avp_timeout_sec=0.2, center_tolerance_rad=0.05)

    centering = pipeline.process(
        HeadPoseSample(head_pose_matrix=make_pose(), timestamp=1.0),
        robot_pose=(0.1, 0.1),
        now=1.0,
    )
    assert centering.state is PipelineState.CENTERING

    calibrating = pipeline.process(
        HeadPoseSample(head_pose_matrix=make_pose(), timestamp=1.05),
        robot_pose=(0.0, 0.0),
        now=1.05,
    )
    assert calibrating.state is PipelineState.TRACKING

    first = calibrating
    assert first.state is PipelineState.TRACKING

    hold = pipeline.process(None, robot_pose=(0.0, 0.0), now=1.4)
    assert hold.state is PipelineState.HOLD
    assert hold.neck_target is None

    recovered = pipeline.process(
        HeadPoseSample(head_pose_matrix=make_pose(0.3), timestamp=1.5),
        robot_pose=(0.4, -0.2),
        now=1.5,
    )
    assert recovered.state is PipelineState.TRACKING
    assert recovered.reason == "realigned"
    assert recovered.neck_target == (0.4, -0.2)


def test_pipeline_auto_tracks_immediately_when_robot_is_already_centered_and_sample_is_available():
    retargeter = FakeRetargeter(outputs=[(0.2, 0.05)])
    pipeline = HeadPosePipeline(retargeter=retargeter, avp_timeout_sec=0.2)

    result = pipeline.process(
        HeadPoseSample(head_pose_matrix=make_pose(0.2), timestamp=1.0),
        robot_pose=(0.0, 0.0),
        now=1.0,
    )

    assert result.state is PipelineState.TRACKING
    assert result.reason == "auto_synced"
    assert retargeter.synced is not None


def test_pipeline_requires_centering_before_calibration_and_tracking():
    retargeter = FakeRetargeter(outputs=[(0.2, 0.05)])
    pipeline = HeadPosePipeline(retargeter=retargeter, avp_timeout_sec=0.2, center_tolerance_rad=0.05)

    centering = pipeline.process(
        HeadPoseSample(head_pose_matrix=make_pose(0.1), timestamp=1.0),
        robot_pose=(0.2, 0.1),
        now=1.0,
    )
    assert centering.state is PipelineState.CENTERING
    assert centering.reason == "centering"

    calibrating = pipeline.process(
        HeadPoseSample(head_pose_matrix=make_pose(0.1), timestamp=1.1),
        robot_pose=(0.01, -0.01),
        now=1.1,
    )
    assert calibrating.state is PipelineState.TRACKING
    assert calibrating.reason == "auto_synced"

    tracking = calibrating
    assert tracking.state is PipelineState.TRACKING
    assert tracking.reason == "auto_synced"
    assert tracking.neck_target == (0.01, -0.01)


def test_pipeline_waits_in_syncing_state_until_sample_arrives():
    pipeline = HeadPosePipeline(retargeter=FakeRetargeter(outputs=[]), avp_timeout_sec=0.2)

    result = pipeline.process(
        None,
        robot_pose=(0.0, 0.0),
        now=1.0,
    )

    assert result.state is PipelineState.SYNCING
    assert result.reason == "waiting_for_sample"


def test_request_resync_returns_pipeline_to_centering():
    retargeter = FakeRetargeter(outputs=[(0.2, 0.05)])
    pipeline = HeadPosePipeline(retargeter=retargeter, avp_timeout_sec=0.2, center_tolerance_rad=0.05)

    pipeline.process(
        HeadPoseSample(head_pose_matrix=make_pose(0.1), timestamp=1.0),
        robot_pose=(0.2, 0.1),
        now=1.0,
    )
    pipeline.process(
        HeadPoseSample(head_pose_matrix=make_pose(0.1), timestamp=1.1),
        robot_pose=(0.0, 0.0),
        now=1.1,
    )

    pipeline.request_resync()

    assert pipeline.state is PipelineState.CENTERING


def test_motor_adapter_initialization_preserves_current_pose_before_torque_enable():
    io = FakeMotorIO()
    adapter = MotorAdapter(
        motor_io=io,
        yaw_motor_id=1,
        pitch_motor_id=2,
        enable_profiles=True,
        profile_velocity=0,
        profile_acceleration=500,
    )

    adapter.initialize()

    assert io.calls[:6] == [
        ("enable_torque", 1, False),
        ("set_operating_mode", 1, 3),
        ("enable_torque", 2, False),
        ("set_operating_mode", 2, 3),
        ("set_goal_positions", {1: 2100, 2: 1900}),
        ("enable_torque", 1, True),
    ]
    assert ("enable_torque", 2, True) in io.calls


def test_motor_adapter_stop_disables_torque_and_closes():
    io = FakeMotorIO()
    adapter = MotorAdapter(motor_io=io, yaw_motor_id=1, pitch_motor_id=2)

    adapter.stop()

    assert io.calls == [
        ("enable_torque", 1, False),
        ("enable_torque", 2, False),
        ("close",),
    ]


def test_motor_adapter_raises_when_present_position_read_fails():
    class MissingPositionIO(FakeMotorIO):
        def get_present_position(self, motor_id):
            return None

    adapter = MotorAdapter(motor_io=MissingPositionIO(), yaw_motor_id=1, pitch_motor_id=2)

    try:
        adapter.get_present_positions()
    except RuntimeError as exc:
        assert "present position" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when motor position read fails")
