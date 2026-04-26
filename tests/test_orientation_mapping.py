import os
import sys

import numpy as np


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

from src.utils.orientation import extract_avp_head_angles
from src.utils.retargeting import HeadRetargeter


YUP2ZUP = np.array(
    [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, -1.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
)


def rot_x(angle):
    c = np.cos(angle)
    s = np.sin(angle)
    return np.array(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, c, -s, 0.0],
            [0.0, s, c, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )


def rot_y(angle):
    c = np.cos(angle)
    s = np.sin(angle)
    return np.array(
        [
            [c, 0.0, s, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [-s, 0.0, c, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )


def make_streamed_head_pose(yaw_rad=0.0, pitch_rad=0.0):
    source = rot_y(yaw_rad) @ rot_x(pitch_rad)
    return YUP2ZUP @ source @ rot_x(np.deg2rad(-90.0))


def test_extract_avp_head_angles_preserves_yaw_after_streamer_axis_transform():
    yaw, pitch = extract_avp_head_angles(make_streamed_head_pose(yaw_rad=0.35))

    assert np.isclose(yaw, 0.35, atol=1e-6)
    assert np.isclose(pitch, 0.0, atol=1e-6)


def test_extract_avp_head_angles_preserves_pitch_after_streamer_axis_transform():
    yaw, pitch = extract_avp_head_angles(make_streamed_head_pose(pitch_rad=0.2))

    assert np.isclose(yaw, 0.0, atol=1e-6)
    assert np.isclose(pitch, 0.2, atol=1e-6)


def test_retargeter_generates_non_zero_yaw_from_streamed_head_pose():
    retargeter = HeadRetargeter()
    retargeter._pending_calibration = False
    retargeter.calibrated = True
    retargeter.yaw_offset = 0.0
    retargeter.pitch_offset = 0.0

    yaw_target, pitch_target = retargeter.compute_neck_target(make_streamed_head_pose(yaw_rad=0.4))

    assert np.isclose(yaw_target, -0.4, atol=1e-6)
    assert np.isclose(pitch_target, 0.0, atol=1e-6)
