import os
import sys

import numpy as np


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

from src.utils.retargeting import HeadRetargeter


def make_pose(yaw_rad=0.0, pitch_rad=0.0):
    cy = np.cos(yaw_rad)
    sy = np.sin(yaw_rad)
    cp = np.cos(pitch_rad)
    sp = np.sin(pitch_rad)

    yaw = np.array(
        [
            [cy, -sy, 0.0, 0.0],
            [sy, cy, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )
    pitch = np.array(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, cp, -sp, 0.0],
            [0.0, sp, cp, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )
    return yaw @ pitch


def test_sync_to_robot_pose_aligns_next_target_with_robot_pose():
    retargeter = HeadRetargeter()
    retargeter.sync_to_robot_pose(
        make_pose(yaw_rad=0.2, pitch_rad=-0.1),
        robot_pose=(0.35, -0.25),
    )

    yaw_target, pitch_target = retargeter.compute_neck_target(make_pose(yaw_rad=0.2, pitch_rad=-0.1))

    assert np.isclose(yaw_target, 0.35, atol=1e-6)
    assert np.isclose(pitch_target, -0.25, atol=1e-6)


def test_request_resync_clears_tracking_offsets_without_touching_smoothers():
    retargeter = HeadRetargeter()
    retargeter.sync_to_robot_pose(make_pose(yaw_rad=0.2), robot_pose=(0.1, 0.0))

    retargeter.request_resync()

    assert retargeter.calibrated is False
    assert retargeter.yaw_offset == 0.0
    assert retargeter.pitch_offset == 0.0


def test_off_mode_ignores_base_imu_compensation():
    retargeter = HeadRetargeter(base_imu_compensation_mode="off")

    yaw_target, pitch_target = retargeter.compute_neck_target(
        make_pose(yaw_rad=0.2, pitch_rad=-0.1),
        base_imu_rpy=(0.15, -0.05, 0.0),
    )

    assert np.isclose(yaw_target, -0.2, atol=1e-6)
    assert np.isclose(pitch_target, 0.1, atol=1e-6)


def test_pitch_only_mode_only_compensates_pitch():
    retargeter = HeadRetargeter(base_imu_compensation_mode="pitch_only")

    yaw_target, pitch_target = retargeter.compute_neck_target(
        make_pose(yaw_rad=0.2, pitch_rad=-0.1),
        base_imu_rpy=(0.15, -0.05, 0.0),
    )

    assert np.isclose(yaw_target, -0.2, atol=1e-6)
    assert np.isclose(pitch_target, 0.15, atol=1e-6)


def test_yaw_pitch_mode_compensates_both_axes():
    retargeter = HeadRetargeter(base_imu_compensation_mode="yaw_pitch")

    yaw_target, pitch_target = retargeter.compute_neck_target(
        make_pose(yaw_rad=0.2, pitch_rad=-0.1),
        base_imu_rpy=(0.15, -0.05, 0.0),
    )

    assert np.isclose(yaw_target, -0.35, atol=1e-6)
    assert np.isclose(pitch_target, 0.15, atol=1e-6)


def test_sync_to_robot_pose_respects_active_compensation_mode():
    retargeter = HeadRetargeter(base_imu_compensation_mode="pitch_only")
    pose = make_pose(yaw_rad=0.2, pitch_rad=-0.1)
    base_imu = (0.15, -0.05, 0.0)
    retargeter.sync_to_robot_pose(
        pose,
        robot_pose=(0.4, -0.25),
        base_imu_rpy=base_imu,
    )

    yaw_target, pitch_target = retargeter.compute_neck_target(
        pose,
        base_imu_rpy=base_imu,
    )

    assert np.isclose(yaw_target, 0.4, atol=1e-6)
    assert np.isclose(pitch_target, -0.25, atol=1e-6)
