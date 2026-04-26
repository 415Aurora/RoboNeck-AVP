import os
import sys


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

from src.gui.pose_control_logic import (
    build_pose_control_view_state,
    resolve_base_imu,
    build_tracking_start_display,
)


def test_view_state_prefers_disconnected_over_other_status():
    state = build_pose_control_view_state(
        motors_connected=False,
        is_tracking=True,
        manual_adjust_active=True,
    )

    assert state["status_text"] == "Disconnected"
    assert state["capture_enabled"] is False


def test_view_state_enters_manual_adjust_mode_when_torque_is_released():
    state = build_pose_control_view_state(
        motors_connected=True,
        is_tracking=False,
        manual_adjust_active=True,
    )

    assert state["status_text"] == "Manual Adjust"
    assert state["release_enabled"] is False
    assert state["capture_enabled"] is True
    assert "Read Motor Pose" in state["step_message"]


def test_view_state_defaults_to_idle_with_connected_motors():
    state = build_pose_control_view_state(
        motors_connected=True,
        is_tracking=False,
        manual_adjust_active=False,
    )

    assert state["status_text"] == "Idle"
    assert state["release_enabled"] is True
    assert state["capture_enabled"] is False


def test_tracking_start_display_formats_current_previous_and_source():
    display = build_tracking_start_display(
        current_pose={"yaw": 12.25, "pitch": -8.5},
        previous_pose={"yaw": 5.0, "pitch": -3.25},
        path="/tmp/tracking_start_pose.json",
        has_saved_record=True,
    )

    assert display["current_text"] == "Yaw 12.2 deg | Pitch -8.5 deg"
    assert display["previous_text"] == "Yaw 5.0 deg | Pitch -3.2 deg"
    assert display["source_text"] == "Saved record: /tmp/tracking_start_pose.json"


def test_tracking_start_display_marks_config_fallback_when_no_saved_file():
    display = build_tracking_start_display(
        current_pose={"yaw": 0.0, "pitch": 0.0},
        previous_pose={"yaw": 0.0, "pitch": 0.0},
        path="/tmp/tracking_start_pose.json",
        has_saved_record=False,
    )

    assert display["source_text"] == "Config fallback: /tmp/tracking_start_pose.json"


class DummyCameraController:
    def __init__(self):
        self.calls = 0

    def get_imu_data(self):
        self.calls += 1
        return (0.1, 0.2, 0.3)


def test_resolve_base_imu_reads_from_camera_controller_when_enabled():
    camera = DummyCameraController()

    assert resolve_base_imu(camera, imu_enabled=True) == (0.1, 0.2, 0.3)
    assert camera.calls == 1


def test_resolve_base_imu_returns_none_without_camera_or_when_disabled():
    camera = DummyCameraController()

    assert resolve_base_imu(camera, imu_enabled=False) is None
    assert resolve_base_imu(None, imu_enabled=True) is None
    assert camera.calls == 0
