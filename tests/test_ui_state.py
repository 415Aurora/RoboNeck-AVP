import os
import sys


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)


from src.gui.ui_state import SystemSnapshot, derive_dashboard_state


def make_snapshot(**overrides):
    data = {
        "avp_connected": False,
        "camera_connected": False,
        "motor_connected": False,
        "motor_ready": False,
        "motor_reason": "",
        "streaming": False,
        "tracking": False,
        "tracking_paused": False,
        "motor_initialized": False,
        "pose_initialized": False,
        "pose_sample_valid": False,
        "pose_sample_reason": "",
        "pose_sample_fresh": False,
        "last_warning": "",
    }
    data.update(overrides)
    return SystemSnapshot(**data)


def test_dashboard_prioritizes_connecting_motor_as_first_explicit_step():
    state = derive_dashboard_state(make_snapshot())

    assert state.next_step == "下一步：连接电机"
    assert state.connect_motor_enabled is True
    assert state.start_tracking_enabled is False
    assert "电机" in state.blocked_reason


def test_dashboard_requires_avp_check_after_motor_is_connected():
    state = derive_dashboard_state(
        make_snapshot(
            motor_connected=True,
            motor_ready=True,
        )
    )

    assert state.next_step == "下一步：检查 AVP"
    assert state.check_avp_enabled is True
    assert state.connect_camera_enabled is False
    assert state.start_tracking_enabled is False


def test_dashboard_requires_connecting_camera_before_stream():
    state = derive_dashboard_state(
        make_snapshot(
            avp_connected=True,
            pose_sample_valid=True,
            pose_sample_fresh=True,
            motor_connected=True,
            motor_ready=True,
        )
    )

    assert state.next_step == "下一步：连接 ZED 相机"
    assert state.connect_camera_enabled is True
    assert state.start_stream_enabled is False


def test_dashboard_requires_stream_before_motor_initialization():
    state = derive_dashboard_state(
        make_snapshot(
            avp_connected=True,
            camera_connected=True,
            motor_connected=True,
            motor_ready=True,
            pose_sample_valid=True,
            pose_sample_fresh=True,
        )
    )

    assert state.next_step == "下一步：开启传输"
    assert state.start_stream_enabled is True
    assert state.motor_init_enabled is False
    assert state.start_tracking_enabled is False


def test_dashboard_requires_motor_initialization_before_pose_initialization():
    state = derive_dashboard_state(
        make_snapshot(
            avp_connected=True,
            camera_connected=True,
            motor_connected=True,
            motor_ready=True,
            streaming=True,
            pose_sample_valid=True,
            pose_sample_fresh=True,
        )
    )

    assert state.next_step == "下一步：电机初始化"
    assert state.motor_init_enabled is True
    assert state.pose_init_enabled is False
    assert state.start_tracking_enabled is False


def test_dashboard_requires_pose_initialization_before_tracking_can_start():
    state = derive_dashboard_state(
        make_snapshot(
            avp_connected=True,
            camera_connected=True,
            motor_connected=True,
            motor_ready=True,
            streaming=True,
            motor_initialized=True,
            pose_sample_valid=True,
            pose_sample_fresh=True,
        )
    )

    assert state.next_step == "下一步：头姿初始化"
    assert state.pose_init_enabled is True
    assert state.start_tracking_enabled is False
    assert "头姿" in state.blocked_reason


def test_dashboard_marks_system_ready_once_staged_prerequisites_are_met():
    state = derive_dashboard_state(
        make_snapshot(
            avp_connected=True,
            camera_connected=True,
            motor_connected=True,
            motor_ready=True,
            streaming=True,
            motor_initialized=True,
            pose_initialized=True,
            pose_sample_valid=True,
            pose_sample_fresh=True,
        )
    )

    assert state.start_tracking_enabled is True
    assert state.next_step == "下一步：开始跟踪"
    assert state.blocked_reason == ""
    assert "系统就绪" in state.hero_label


def test_dashboard_exposes_stop_and_safe_reset_when_tracking_is_active():
    state = derive_dashboard_state(
        make_snapshot(
            avp_connected=True,
            camera_connected=True,
            motor_connected=True,
            motor_ready=True,
            streaming=True,
            tracking=True,
            motor_initialized=True,
            pose_initialized=True,
            pose_sample_valid=True,
            pose_sample_fresh=True,
        )
    )

    assert state.start_tracking_enabled is False
    assert state.stop_tracking_enabled is True
    assert state.safe_reset_enabled is True
    assert state.next_step == "跟踪运行中，可停止跟踪或安全复位"


def test_dashboard_shows_paused_state_without_reenabling_start():
    state = derive_dashboard_state(
        make_snapshot(
            avp_connected=True,
            camera_connected=True,
            motor_connected=True,
            motor_ready=True,
            streaming=True,
            tracking=True,
            tracking_paused=True,
            motor_initialized=True,
            pose_initialized=True,
            pose_sample_valid=False,
            pose_sample_reason="stale_sample",
            pose_sample_fresh=False,
        )
    )

    assert state.status_tone == "warning"
    assert state.hero_label == "已暂停"
    assert state.start_tracking_enabled is False
    assert state.stop_tracking_enabled is True
    assert "恢复" in state.next_step
    assert "stale_sample" in state.blocked_reason


def test_dashboard_blocks_actions_when_motor_transport_is_connected_but_not_ready():
    state = derive_dashboard_state(
        make_snapshot(
            avp_connected=True,
            camera_connected=True,
            motor_connected=True,
            motor_ready=False,
            motor_reason="无法读取电机当前位置",
            streaming=True,
            pose_sample_valid=True,
            pose_sample_fresh=True,
        )
    )

    assert state.start_tracking_enabled is False
    assert state.motor_init_enabled is False
    assert state.safe_reset_enabled is False
    assert state.status_tone == "warning"
    assert "无法读取电机当前位置" in state.blocked_reason
