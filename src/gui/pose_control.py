import sys
import numpy as np
import time
from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QGridLayout, QLabel, 
    QPushButton, QCheckBox, QHBoxLayout, QMessageBox, QSpinBox, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from config import config
from src.core.calibration import MechanicalCenterCalibration
from src.core.controller import ControlState, HeadPoseSample, NeckController
from src.core.motor_limits import (
    axis_limit_steps,
    clamp_step_target,
    motor_limit_store as build_motor_limit_store,
    pose_limit_violation,
    tracking_start_pose_store as build_tracking_start_pose_store,
    validate_motor_limits,
)
from src.core.paths import get_calibration_path
from src.core.runtime import ControlRuntime
from src.utils.retargeting import HeadRetargeter

def rad_to_steps(rad):
    """Convert radians to steps (4096 scale)."""
    steps_from_center = rad * (config.STEPS_PER_REV / (2 * np.pi))
    target = config.ZERO_POS + steps_from_center
    return int(max(0, min(config.STEPS_PER_REV - 1, target)))


def tracking_start_pose_store():
    return build_tracking_start_pose_store()


def motor_limit_store():
    return build_motor_limit_store()


def _state_age_seconds(status):
    try:
        value = (status or {}).get("state_age_sec", None)
        if value is None:
            return None
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def _format_wait_age(status):
    age_sec = _state_age_seconds(status)
    if age_sec is None:
        return ""
    return f"（已等待 {age_sec:.1f}s）"


def _describe_pose_status(status):
    reason = str((status or {}).get("reason", "") or "unknown")
    error = str((status or {}).get("error", "") or "")
    wait_age = _format_wait_age(status)
    state_age_sec = _state_age_seconds(status)

    if reason == "streamer_initializing":
        if state_age_sec is not None and state_age_sec >= 3.0:
            return (
                f"AVP 正在初始化{wait_age}。Python 端仍在等待与 Vision Pro 完成握手；"
                "请确认 Vision Pro 上的 Tracking Streamer 已打开，并在应用内点击 Start。"
            )
        return f"AVP 正在初始化{wait_age}。请确认 Vision Pro 上的 Tracking Streamer 已打开，并在应用内点击 Start。"
    if reason == "streamer_init_failed":
        suffix = f" 详细错误：{error}" if error else ""
        return f"AVP 初始化失败。请检查 Vision Pro IP、同网段连接和 avp_stream 依赖。{suffix}"
    if reason == "stream_established_waiting_first_sample":
        return (
            f"AVP 链路已建立，但尚未收到首帧头姿{wait_age}。"
            "这表示握手已完成，但 Vision Pro 还没有发送头姿；请确认 Vision Pro 应用保持前台并已点击 Start。"
        )
    if reason == "missing_head_field":
        return "AVP 已连接，但当前数据包中没有头姿字段。"
    if reason == "invalid_head_shape":
        return "AVP 头姿矩阵形状异常。"
    if reason == "invalid_head_values":
        return "AVP 头姿矩阵包含无效数值。"
    if reason == "sample_exception":
        return "读取 AVP 姿态样本时发生异常。"
    if reason == "invalid_payload_type":
        return "AVP 返回了无法识别的数据类型。"
    return f"AVP 姿态样本暂不可用：{reason}"

class PoseControlWidget(QWidget):
    """
    Widget for managing AVP -> Robot Neck pose retargeting.
    Replaces the main loop in app.py.
    """
    runtime_event = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.motor_controller = None # Injected by MainWindow
        self.avp_client = None       # Injected by MainWindow
        self.camera_controller = None
        self.retargeter = HeadRetargeter()
        self.streaming_ready = False
        self.last_motor_commands = {}
        self._tracking_start_store = tracking_start_pose_store()
        self._motor_limit_store = motor_limit_store()
        self._motor_limits = validate_motor_limits(self._motor_limit_store.load())
        self._tracking_start_adjustment_active = False
        self._homing_active = False
        self._homing_target_positions = None
        self._homing_deadline = None
        self._homing_on_success = None
        self._homing_on_failure = None
        self._homing_final_command_sent = False
        self._homing_settle_ticks = 0
        self._last_pause_reason = ""
        
        self.is_tracking = False
        self.is_tracking_paused = False
        self.motor_initialized = False
        self.pose_initialized = False
        self.runtime = None
        self.init_ui()
        self._load_tracking_start_pose()
        self.runtime = self._build_runtime()
        
        # Control Loop Timer (60Hz)
        self.timer = QTimer()
        self.timer.timeout.connect(self.control_loop)
        self.timer.setInterval(int(1000 / config.LOOP_RATE)) 
        self._homing_timer = QTimer()
        self._homing_timer.timeout.connect(self._process_homing_tick)
        self._homing_timer.setInterval(int(1000 / max(1, config.LOOP_RATE)))

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 1. Main Toggle
        grp_main = QGroupBox("姿态跟踪")
        layout_main = QVBoxLayout()
        grp_main.setLayout(layout_main)
        
        self.btn_track = QPushButton("开始跟踪")
        self.btn_track.setCheckable(True)
        self.btn_track.setStyleSheet("background-color: #2ecc71; color: white; height: 40px; font-weight: bold; font-size: 14px;")
        self.btn_track.toggled.connect(self.toggle_tracking)
        layout_main.addWidget(self.btn_track)
        
        layout.addWidget(grp_main)
        
        # 2. Status Display
        grp_status = QGroupBox("实时姿态数据")
        layout_status = QGridLayout()
        grp_status.setLayout(layout_status)
        
        # Head Input
        layout_status.addWidget(QLabel("<b>输入（AVP）</b>"), 0, 1)
        layout_status.addWidget(QLabel("偏航："), 1, 0)
        self.lbl_head_yaw = QLabel("0.0°")
        layout_status.addWidget(self.lbl_head_yaw, 1, 1)
        
        layout_status.addWidget(QLabel("俯仰："), 2, 0)
        self.lbl_head_pitch = QLabel("0.0°")
        layout_status.addWidget(self.lbl_head_pitch, 2, 1)
        
        # Robot Target
        layout_status.addWidget(QLabel("<b>目标（机器人）</b>"), 0, 2)
        self.lbl_robot_yaw = QLabel("0.0°")
        layout_status.addWidget(self.lbl_robot_yaw, 1, 2)
        self.lbl_robot_pitch = QLabel("0.0°")
        layout_status.addWidget(self.lbl_robot_pitch, 2, 2)
        
        layout.addWidget(grp_status)
        
        # 3. Calibration
        grp_calib = QGroupBox("校准")
        layout_calib = QHBoxLayout()
        grp_calib.setLayout(layout_calib)
        
        btn_calib = QPushButton("设置中心位")
        btn_calib.clicked.connect(self.calibrate)
        layout_calib.addWidget(btn_calib)

        layout_calib.addWidget(QLabel("ZED 补偿："))
        self.combo_imu_compensation = QComboBox()
        self.combo_imu_compensation.addItem("关闭补偿", "off")
        self.combo_imu_compensation.addItem("仅 Pitch 补偿", "pitch_only")
        self.combo_imu_compensation.addItem("Yaw + Pitch 补偿", "yaw_pitch")
        self.combo_imu_compensation.setToolTip("切换 ZED IMU 对头姿态目标的补偿模式。")
        self.combo_imu_compensation.currentIndexChanged.connect(self.on_imu_compensation_mode_changed)
        layout_calib.addWidget(self.combo_imu_compensation)
        
        
        # Home Position
        layout_calib.addWidget(QLabel("偏航初始位："))
        self.spin_home_yaw = QSpinBox()
        self.spin_home_yaw.setRange(0, 4096)
        self.spin_home_yaw.setValue(config.ZERO_POS)
        self.spin_home_yaw.setToolTip("偏航跟踪初始位置（默认 2048）")
        layout_calib.addWidget(self.spin_home_yaw)

        layout_calib.addWidget(QLabel("俯仰初始位："))
        self.spin_home_pitch = QSpinBox()
        self.spin_home_pitch.setRange(0, 4096)
        self.spin_home_pitch.setValue(config.ZERO_POS)
        self.spin_home_pitch.setToolTip("俯仰跟踪初始位置（默认 2048）")
        layout_calib.addWidget(self.spin_home_pitch)

        btn_prepare_start_pose = QPushButton("释放舵机设置初始位")
        btn_prepare_start_pose.clicked.connect(self.begin_tracking_start_pose_adjustment)
        layout_calib.addWidget(btn_prepare_start_pose)

        btn_read_start_pose = QPushButton("读取当前位置")
        btn_read_start_pose.clicked.connect(self.read_tracking_start_pose_from_motors)
        layout_calib.addWidget(btn_read_start_pose)

        btn_save_start_pose = QPushButton("保存跟踪初始位")
        btn_save_start_pose.clicked.connect(self.save_tracking_start_pose)
        layout_calib.addWidget(btn_save_start_pose)

        btn_reset_calib = QPushButton("重置校准")
        btn_reset_calib.clicked.connect(self.reset_calibration)
        layout_calib.addWidget(btn_reset_calib)
        
        layout.addWidget(grp_calib)
        
        layout.addStretch()
        self._sync_imu_compensation_mode_ui()

    def set_dependencies(self, motors, client, camera_controller=None):
        if motors is not self.motor_controller:
            self.motor_initialized = False
            self.pose_initialized = False
        self.motor_controller = motors
        self.avp_client = client
        self.camera_controller = camera_controller

    def set_streaming_ready(self, ready):
        self.streaming_ready = bool(ready)

    def _motor_transport_connected(self):
        return bool(self.motor_controller and getattr(self.motor_controller, "connected", False))

    def _motor_motion_ready(self):
        return bool(self._motor_transport_connected() and getattr(self.motor_controller, "motors_ready", True))

    def _motor_unavailable_message(self):
        if not self._motor_transport_connected():
            return "电机未连接。"
        reason = getattr(self.motor_controller, "motor_error", "") if self.motor_controller else ""
        if reason:
            return f"电机未就绪：{reason}"
        return "电机未就绪，请检查电机供电、接线、ID 和波特率。"

    def _build_runtime(self):
        centers = MechanicalCenterCalibration(
            path=get_calibration_path(),
            default_yaw_center=config.ZERO_POS,
            default_pitch_center=config.ZERO_POS,
        ).load()
        controller = NeckController(
            yaw_motor_id=config.YAW_MOTOR_ID,
            pitch_motor_id=config.PITCH_MOTOR_ID,
            zero_pos=config.ZERO_POS,
            steps_per_rev=config.STEPS_PER_REV,
            yaw_limit_deg=config.YAW_LIMIT_DEG,
            pitch_limit_deg=config.PITCH_LIMIT_DEG,
            yaw_scale=config.YAW_SCALE,
            pitch_scale=config.PITCH_SCALE,
            initial_pose=config.INITIAL_POSE,
            max_step_change=config.MAX_STEP_CHANGE,
            avp_timeout_sec=config.AVP_TIMEOUT_SEC,
            retargeter=self.retargeter,
            yaw_deadzone_deg=config.YAW_DEADZONE_DEG,
            pitch_deadzone_deg=config.PITCH_DEADZONE_DEG,
            centering_max_step_change=config.CENTERING_MAX_STEP_CHANGE,
            yaw_center_step=centers["yaw_center_step"],
            pitch_center_step=centers["pitch_center_step"],
            yaw_limit_steps=(self._motor_limits["yaw_min_step"], self._motor_limits["yaw_max_step"]),
            pitch_limit_steps=(self._motor_limits["pitch_min_step"], self._motor_limits["pitch_max_step"]),
            max_accel_step_change=getattr(config, "MAX_COMMAND_ACCEL_STEP", config.MAX_STEP_CHANGE),
        )
        return ControlRuntime(
            controller=controller,
            tracking_start_positions=self._tracking_start_positions(),
            centering_step_tolerance=getattr(config, "CENTERING_STEP_TOLERANCE", 8),
            io_fault_threshold=getattr(config, "IO_FAULT_THRESHOLD", 3),
        )

    def _sync_runtime_retargeter(self):
        if self.runtime and getattr(self.runtime, "controller", None):
            self.runtime.controller.retargeter = self.retargeter

    def _apply_base_imu_compensation_mode(self, mode):
        if hasattr(self.retargeter, "set_base_imu_compensation_mode"):
            self.retargeter.set_base_imu_compensation_mode(mode)
        else:
            self.retargeter.base_imu_compensation_mode = mode
        self._sync_runtime_retargeter()

    def _sync_imu_compensation_mode_ui(self):
        mode = getattr(self.retargeter, "base_imu_compensation_mode", getattr(config, "ZED_IMU_COMPENSATION_MODE", "off"))
        index = self.combo_imu_compensation.findData(mode)
        if index >= 0:
            self.combo_imu_compensation.setCurrentIndex(index)
        else:
            self._apply_base_imu_compensation_mode("off")
            fallback_index = self.combo_imu_compensation.findData("off")
            if fallback_index >= 0:
                self.combo_imu_compensation.setCurrentIndex(fallback_index)

    def on_imu_compensation_mode_changed(self, _index):
        mode = self.combo_imu_compensation.currentData()
        if mode is None:
            return
        self._apply_base_imu_compensation_mode(mode)

    def _load_tracking_start_pose(self):
        pose = self._tracking_start_store.load()
        self.spin_home_yaw.setValue(int(pose["yaw_start_step"]))
        self.spin_home_pitch.setValue(int(pose["pitch_start_step"]))
        if self.runtime:
            self.runtime.update_tracking_start_positions(self._tracking_start_positions())

    def set_motor_limits(self, limits):
        self._motor_limits = validate_motor_limits(limits)
        if self.runtime:
            self.runtime.controller.set_step_limits(
                self._motor_limits["yaw_min_step"],
                self._motor_limits["yaw_max_step"],
                self._motor_limits["pitch_min_step"],
                self._motor_limits["pitch_max_step"],
            )

    def reload_motor_limits(self):
        self.set_motor_limits(self._motor_limit_store.load())

    def _tracking_start_positions(self):
        return {
            config.YAW_MOTOR_ID: int(self.spin_home_yaw.value()),
            config.PITCH_MOTOR_ID: int(self.spin_home_pitch.value()),
        }

    def _validate_tracking_start_positions(self):
        home_positions = self._tracking_start_positions()
        warning = pose_limit_violation(
            self._motor_limits,
            home_positions[config.YAW_MOTOR_ID],
            home_positions[config.PITCH_MOTOR_ID],
        )
        if warning:
            self._warn("警告", warning)
            return None
        return home_positions

    def _set_tracking_start_adjustment_mode(self, active):
        self._tracking_start_adjustment_active = bool(active)
        if active:
            self.motor_initialized = False
            self.pose_initialized = False

    def _set_homing_active(self, active):
        self._homing_active = bool(active)

    def _centering_step_tolerance(self):
        return int(max(0, getattr(config, "CENTERING_STEP_TOLERANCE", 8)))

    def _final_centering_step_tolerance(self):
        return int(max(0, getattr(config, "CENTERING_FINAL_STEP_TOLERANCE", 3)))

    def _centering_settle_ticks(self):
        return int(max(1, getattr(config, "CENTERING_SETTLE_TICKS", 2)))

    def _centering_timeout_sec(self):
        return float(max(0.1, getattr(config, "CENTERING_TIMEOUT_SEC", 5.0)))

    def _is_timer_active(self, timer):
        if hasattr(timer, "isActive"):
            return bool(timer.isActive())
        return bool(getattr(timer, "running", False))

    def _motor_axis_label(self, motor_id):
        return "偏航轴" if motor_id == config.YAW_MOTOR_ID else "俯仰轴"

    def _normalize_torque_result(self, motor_id, enabled, result):
        action = "使能" if enabled else "关闭"
        default_error = f"无法{action}电机 ID {motor_id} 的扭矩。"
        if isinstance(result, tuple):
            ok = bool(result[0])
            error = str(result[1]) if len(result) > 1 and result[1] else ""
        elif result is None:
            ok = True
            error = ""
        else:
            ok = bool(result)
            error = "" if ok else default_error

        if not ok and not error:
            error = default_error
        return ok, error

    def _set_motor_torque_for_axis(self, motor_id, enabled):
        action = "使能" if enabled else "关闭"
        if not self._motor_transport_connected():
            return False, "串口未连接。"
        if not hasattr(self.motor_controller, "enable_torque"):
            return False, "电机控制器不支持扭矩控制。"

        try:
            result = self.motor_controller.enable_torque(motor_id, enabled)
        except Exception as exc:
            return False, f"无法{action}电机 ID {motor_id} 的扭矩：{exc}"
        return self._normalize_torque_result(motor_id, enabled, result)

    def _set_motor_torque_all_axes(self, enabled, require_motion_ready=True):
        if require_motion_ready and not self._motor_motion_ready():
            return False, [
                (
                    None,
                    self._motor_unavailable_message(),
                )
            ]
        if not self._motor_transport_connected():
            return False, [(None, "电机未连接。")]

        failures = []
        success_count = 0
        for motor_id in (config.YAW_MOTOR_ID, config.PITCH_MOTOR_ID):
            ok, error = self._set_motor_torque_for_axis(motor_id, enabled)
            if ok:
                success_count += 1
            else:
                failures.append((motor_id, error))
        return success_count > 0, failures

    def _format_axis_failures(self, failures):
        parts = []
        for motor_id, error in failures:
            if motor_id is None:
                parts.append(str(error))
            else:
                prefix = self._motor_axis_label(motor_id)
                if error:
                    parts.append(f"{prefix}：{error}")
                else:
                    parts.append(f"{prefix}操作失败。")
        return "；".join(parts)

    def _set_motor_torque_enabled(self, enabled):
        any_success, failures = self._set_motor_torque_all_axes(enabled, require_motion_ready=True)
        return bool(any_success and not failures)

    def begin_tracking_start_pose_adjustment(self):
        if self._homing_active:
            self._cancel_homing()
        if self.is_tracking:
            self._set_tracking_active(False)

        if not self._motor_transport_connected():
            self._warn("警告", f"{self._motor_unavailable_message()} 无法进入初始位手动设置模式。")
            return False

        any_success, failures = self._set_motor_torque_all_axes(False, require_motion_ready=False)
        if not any_success:
            details = self._format_axis_failures(failures)
            message = "无法进入初始位手动设置模式。"
            if details:
                message = f"{message} {details}"
            self._warn("警告", message)
            return False

        self._set_tracking_start_adjustment_mode(True)
        prompt = "请手动调整到期望初始位，然后读取当前位置或手动输入。"
        if failures or not self._motor_motion_ready():
            details = self._format_axis_failures(failures)
            message = f"{self._motor_unavailable_message()} 已尽力关闭扭矩，{prompt}"
            if details:
                message = f"{message} {details}"
            self._warn("警告", message)
        else:
            QMessageBox.information(self, "完成", f"两轴扭矩已关闭，{prompt}")
        return True

    def read_tracking_start_pose_from_motors(self):
        if not self._motor_motion_ready():
            self._warn("警告", self._motor_unavailable_message())
            return False
        positions = self._get_present_positions()
        if positions is None:
            self._warn("警告", self._motor_unavailable_message())
            return False

        self.spin_home_yaw.setValue(int(positions[config.YAW_MOTOR_ID]))
        self.spin_home_pitch.setValue(int(positions[config.PITCH_MOTOR_ID]))
        return True

    def save_tracking_start_pose(self):
        home_positions = self._validate_tracking_start_positions()
        if home_positions is None:
            return False

        saved = self._tracking_start_store.save(
            home_positions[config.YAW_MOTOR_ID],
            home_positions[config.PITCH_MOTOR_ID],
        )
        if self._tracking_start_adjustment_active:
            _any_success, failures = self._set_motor_torque_all_axes(True, require_motion_ready=False)
            self._set_tracking_start_adjustment_mode(False)
            if failures:
                details = self._format_axis_failures(failures)
                self._warn("警告", f"跟踪初始位已保存，但重新上扭矩时存在失败轴：{details}")
        if self.runtime:
            self.runtime.update_tracking_start_positions(home_positions)
        self.motor_initialized = False
        self.pose_initialized = False
        QMessageBox.information(self, "完成", f"跟踪初始位已保存：{saved}")
        return True

    def _set_track_button_checked(self, checked):
        if not hasattr(self.btn_track, "setChecked"):
            return

        if hasattr(self.btn_track, "blockSignals"):
            previous = self.btn_track.blockSignals(True)
            self.btn_track.setChecked(checked)
            self.btn_track.blockSignals(previous)
            return

        if hasattr(self.btn_track, "_checked"):
            self.btn_track._checked = checked
            return

        self.btn_track.setChecked(checked)

    def _set_tracking_active(self, active):
        self._set_track_button_checked(active)
        if active:
            self.btn_track.setText("停止跟踪")
            self.btn_track.setStyleSheet("background-color: #e74c3c; color: white; height: 40px; font-weight: bold; font-size: 14px;")
            self.is_tracking = True
            self.timer.start()
        else:
            self.btn_track.setText("开始跟踪")
            self.btn_track.setStyleSheet("background-color: #2ecc71; color: white; height: 40px; font-weight: bold; font-size: 14px;")
            self.is_tracking = False
            self.timer.stop()
        if not active:
            self.is_tracking_paused = False
            self._last_pause_reason = ""

    def _update_tracking_pause_state(self):
        runtime_status = self.runtime.get_status() if self.runtime else None
        self.is_tracking_paused = bool(runtime_status and runtime_status.tracking_paused and self.is_tracking)
        return runtime_status

    def _emit_runtime_event(self, level, message):
        self.runtime_event.emit(str(level), str(message))

    def _format_hold_commands(self, commands):
        if not commands:
            return "unknown"
        yaw = commands.get(config.YAW_MOTOR_ID, "na")
        pitch = commands.get(config.PITCH_MOTOR_ID, "na")
        return f"{yaw},{pitch}"

    def _warn(self, title, message):
        QMessageBox.warning(self, title, message)

    def _get_present_positions(self):
        if not self._motor_transport_connected():
            return None

        yaw_steps = self.motor_controller.get_present_position(config.YAW_MOTOR_ID)
        pitch_steps = self.motor_controller.get_present_position(config.PITCH_MOTOR_ID)
        if yaw_steps is None or pitch_steps is None:
            if hasattr(self.motor_controller, "set_motor_readiness"):
                self.motor_controller.set_motor_readiness(
                    False,
                    "无法读取电机当前位置，请检查电机供电、接线、ID 和波特率。",
                )
            return None

        if hasattr(self.motor_controller, "set_motor_readiness"):
            self.motor_controller.set_motor_readiness(True, "")

        return {
            config.YAW_MOTOR_ID: int(yaw_steps),
            config.PITCH_MOTOR_ID: int(pitch_steps),
        }

    def _get_robot_pose_radians(self):
        positions = self._get_present_positions()
        if positions is None:
            return None

        if self.runtime:
            yaw_rad = self.runtime.controller.steps_to_radians(positions[config.YAW_MOTOR_ID], axis="yaw")
            pitch_rad = self.runtime.controller.steps_to_radians(positions[config.PITCH_MOTOR_ID], axis="pitch")
            return yaw_rad, pitch_rad

        yaw_rad = (positions[config.YAW_MOTOR_ID] - config.ZERO_POS) * (2 * np.pi / config.STEPS_PER_REV) / config.YAW_SCALE
        pitch_rad = (positions[config.PITCH_MOTOR_ID] - config.ZERO_POS) * (2 * np.pi / config.STEPS_PER_REV) / config.PITCH_SCALE
        return yaw_rad, pitch_rad

    def _axis_limit_steps(self, axis):
        return axis_limit_steps(self._motor_limits, axis)

    def _clamp_steps_to_limits(self, axis, target_steps):
        return clamp_step_target(self._motor_limits, axis, target_steps)

    def _capture_head_pose_for_sync(self, attempts=10, delay_sec=0.01, require_imu=False):
        if not self.avp_client:
            return None

        sample = None
        for _ in range(attempts):
            sample = self._get_latest_head_pose_sample()
            if sample is not None:
                break
            time.sleep(delay_sec)

        if sample is None:
            return None
        if require_imu and sample.base_imu_rpy is None:
            return None
        return sample

    def _sync_to_robot_pose(self, robot_pose):
        mode = getattr(self.retargeter, "base_imu_compensation_mode", "off")
        sample = self._capture_head_pose_for_sync(require_imu=mode != "off")
        if sample is None:
            return False

        self._sync_runtime_retargeter()
        self.retargeter.sync_to_robot_pose(
            sample.head_pose_matrix,
            robot_pose=robot_pose,
            base_imu_rpy=sample.base_imu_rpy,
        )
        if self.runtime:
            self.runtime.controller.robot_synced = True
            self.runtime.resync_required = False
            self.runtime.mode = ControlState.READY
        self.pose_initialized = True
        return True

    def initialize_pose_sync(self):
        if not self.streaming_ready:
            return False
        if not self._motor_motion_ready():
            return False
        if not self.avp_client:
            return False
        if not self.motor_initialized:
            return False
        return bool(self._sync_to_robot_pose((0.0, 0.0)))

    def _get_latest_head_pose_sample(self):
        if not self.avp_client:
            return None

        if hasattr(self.avp_client, "get_latest_head_pose_sample"):
            sample = self.avp_client.get_latest_head_pose_sample()
            if sample is not None:
                return sample

        if not hasattr(self.avp_client, "get_latest_head_pose_matrix"):
            return None

        pose_matrix = self.avp_client.get_latest_head_pose_matrix()
        if pose_matrix is None:
            return None

        return HeadPoseSample(
            head_pose_matrix=pose_matrix,
            timestamp=time.monotonic(),
            base_imu_rpy=self.avp_client.get_camera_imu() if hasattr(self.avp_client, "get_camera_imu") else None,
            raw_payload={"fallback_matrix": True},
            fresh=True,
            source_timestamp=None,
        )

    def _get_pose_status(self):
        if self.avp_client and hasattr(self.avp_client, "get_pose_status"):
            status = self.avp_client.get_pose_status() or {}
            return {
                "valid": bool(status.get("valid", False)),
                "reason": status.get("reason", ""),
                "fresh": bool(status.get("fresh", False)),
                "error": status.get("error", ""),
                "state_age_sec": status.get("state_age_sec"),
            }
        return {"valid": False, "reason": "", "fresh": False, "error": "", "state_age_sec": None}

    def _build_pose_unavailable_message(self, prefix):
        status = self._get_pose_status()
        return f"{prefix} {_describe_pose_status(status)}"

    def _apply_step_limit(self, motor_id, target_steps, current_steps, max_step_change):
        previous = self.last_motor_commands.get(motor_id, current_steps)
        delta = int(target_steps) - int(previous)
        if abs(delta) <= max_step_change:
            limited = int(target_steps)
        else:
            limited = int(previous + np.sign(delta) * max_step_change)
        self.last_motor_commands[motor_id] = limited
        return limited

    def _build_limited_motor_commands(self, yaw_target_rad, pitch_target_rad, motor_positions, max_step_change):
        yaw_deg = np.rad2deg(yaw_target_rad * config.YAW_SCALE)
        pitch_deg = np.rad2deg(pitch_target_rad * config.PITCH_SCALE)

        yaw_target_steps = self._clamp_steps_to_limits("yaw", rad_to_steps(np.deg2rad(yaw_deg)))
        pitch_target_steps = self._clamp_steps_to_limits("pitch", rad_to_steps(np.deg2rad(pitch_deg)))

        return {
            config.YAW_MOTOR_ID: self._apply_step_limit(
                config.YAW_MOTOR_ID,
                yaw_target_steps,
                motor_positions[config.YAW_MOTOR_ID],
                max_step_change=max_step_change,
            ),
            config.PITCH_MOTOR_ID: self._apply_step_limit(
                config.PITCH_MOTOR_ID,
                pitch_target_steps,
                motor_positions[config.PITCH_MOTOR_ID],
                max_step_change=max_step_change,
            ),
        }

    def _build_centering_commands(self, target_positions, motor_positions, max_step_change):
        commands = {}
        for motor_id, axis in (
            (config.YAW_MOTOR_ID, "yaw"),
            (config.PITCH_MOTOR_ID, "pitch"),
        ):
            limited_target = self._clamp_steps_to_limits(axis, target_positions[motor_id])
            commands[motor_id] = self._apply_step_limit(
                motor_id,
                limited_target,
                motor_positions[motor_id],
                max_step_change=max_step_change,
            )
        return commands

    def _send_motor_commands(self, commands):
        if not commands or not self.motor_controller:
            return

        if hasattr(self.motor_controller, 'set_goal_positions'):
            self.motor_controller.set_goal_positions(commands)
        else:
            for mid, pos in commands.items():
                if hasattr(self.motor_controller, 'set_goal_position'):
                    self.motor_controller.set_goal_position(mid, pos)

    def _home_positions_within_tolerance(self, motor_positions, target_positions, tolerance=None):
        tolerance = self._centering_step_tolerance() if tolerance is None else int(max(0, tolerance))
        return (
            abs(int(motor_positions[config.YAW_MOTOR_ID]) - int(target_positions[config.YAW_MOTOR_ID])) <= tolerance
            and abs(int(motor_positions[config.PITCH_MOTOR_ID]) - int(target_positions[config.PITCH_MOTOR_ID])) <= tolerance
        )

    def _cancel_homing(self):
        if self._is_timer_active(self._homing_timer):
            self._homing_timer.stop()
        self._set_homing_active(False)
        self._homing_target_positions = None
        self._homing_deadline = None
        self._homing_on_success = None
        self._homing_on_failure = None
        self._homing_final_command_sent = False
        self._homing_settle_ticks = 0

    def _finish_homing(self, success, payload):
        on_success = self._homing_on_success
        on_failure = self._homing_on_failure
        self._cancel_homing()
        if success:
            if on_success:
                on_success(payload)
            return True
        if on_failure:
            on_failure(payload)
        return False

    def _process_homing_tick(self):
        if not self._homing_active or self._homing_target_positions is None:
            return

        motor_positions = self._get_present_positions()
        if motor_positions is None:
            self._finish_homing(False, self._motor_unavailable_message())
            return

        if time.monotonic() >= self._homing_deadline:
            yaw_delta = abs(int(motor_positions[config.YAW_MOTOR_ID]) - int(self._homing_target_positions[config.YAW_MOTOR_ID]))
            pitch_delta = abs(int(motor_positions[config.PITCH_MOTOR_ID]) - int(self._homing_target_positions[config.PITCH_MOTOR_ID]))
            self._finish_homing(
                False,
                f"电机未在 {self._centering_timeout_sec():.1f}s 内进入跟踪初始位（偏航差 {yaw_delta} 步，俯仰差 {pitch_delta} 步）。",
            )
            return

        coarse_aligned = self._home_positions_within_tolerance(
            motor_positions,
            self._homing_target_positions,
            tolerance=self._centering_step_tolerance(),
        )

        if coarse_aligned:
            self._homing_settle_ticks += 1
            if self._homing_settle_ticks >= self._centering_settle_ticks():
                self._finish_homing(True, dict(motor_positions))
                return
            return

        self._homing_settle_ticks = 0

        commands = self._build_centering_commands(
            self._homing_target_positions,
            motor_positions,
            max_step_change=config.CENTERING_MAX_STEP_CHANGE,
        )
        self._send_motor_commands(commands)

        updated_positions = self._get_present_positions()
        if updated_positions is not None and self._home_positions_within_tolerance(
            updated_positions,
            self._homing_target_positions,
            tolerance=self._centering_step_tolerance(),
        ):
            self._homing_settle_ticks = 1

    def _start_homing(self, target_positions, on_success, on_failure):
        if self._homing_active:
            if on_failure:
                on_failure("回中进行中，请稍候。")
            return False

        if not self._motor_motion_ready():
            if on_failure:
                on_failure(self._motor_unavailable_message())
            return False

        motor_positions = self._get_present_positions()
        if motor_positions is None:
            if on_failure:
                on_failure(self._motor_unavailable_message())
            return False

        self.last_motor_commands = dict(motor_positions)
        self._homing_target_positions = dict(target_positions)
        self._homing_deadline = time.monotonic() + self._centering_timeout_sec()
        self._homing_on_success = on_success
        self._homing_on_failure = on_failure
        self._homing_final_command_sent = False
        self._homing_settle_ticks = 0
        self._set_homing_active(True)

        self._process_homing_tick()
        if self._homing_active and not self._is_timer_active(self._homing_timer):
            self._homing_timer.start()
        return True

    def _start_homing_to_tracking_start(self, on_success, on_failure):
        home_positions = self._validate_tracking_start_positions()
        if home_positions is None:
            return False
        return self._start_homing(home_positions, on_success=on_success, on_failure=on_failure)

    def _update_robot_pose_labels_from_steps(self, yaw_step, pitch_step):
        yaw_deg = (int(yaw_step) - config.ZERO_POS) * (360.0 / config.STEPS_PER_REV)
        pitch_deg = (int(pitch_step) - config.ZERO_POS) * (360.0 / config.STEPS_PER_REV)
        self.lbl_robot_yaw.setText(f"{yaw_deg:.1f}°")
        self.lbl_robot_pitch.setText(f"{pitch_deg:.1f}°")

    def move_to_tracking_start_pose(self):
        def on_success(_positions):
            self._update_robot_pose_labels_from_steps(
                self.spin_home_yaw.value(),
                self.spin_home_pitch.value(),
            )
            self.motor_initialized = True
            self.pose_initialized = False

        def on_failure(message):
            self._warn("警告", f"无法移动到已保存的追踪初始位：{message}")

        return self._start_homing_to_tracking_start(on_success=on_success, on_failure=on_failure)

    def start_tracking_sequence(self):
        if not self.streaming_ready:
            self._set_tracking_active(False)
            self._warn("Warning", "Video stream is not ready. Start streaming before tracking.")
            return False

        if not self._motor_motion_ready():
            self._set_tracking_active(False)
            self._warn("Warning", self._motor_unavailable_message())
            return False

        if not self.avp_client:
            self._set_tracking_active(False)
            self._warn("Warning", "AVP client is not ready.")
            return False

        self._sync_runtime_retargeter()
        if self.runtime:
            self.runtime.update_tracking_start_positions(self._tracking_start_positions())
        self._emit_runtime_event("info", "[TRACK] START_REQUEST")

        def on_success(_positions):
            motor_positions = self._get_present_positions()
            if motor_positions is None:
                self._emit_runtime_event("error", f"[MOTOR] PRESENT_POS_READ_FAIL reason={self._motor_unavailable_message()}")
                self._set_tracking_active(False)
                self._warn("Warning", self._motor_unavailable_message())
                return

            sample = self._get_latest_head_pose_sample()
            result = None
            if self.runtime:
                tick_now = sample.timestamp if sample is not None and sample.timestamp is not None else time.monotonic()
                self.runtime.request_start_tracking()
                result = self.runtime.tick(sample=sample, motor_positions=motor_positions, now=tick_now)
            if result is None or result.state is not ControlState.TRACKING:
                self._set_tracking_active(False)
                self._warn("Warning", self._build_pose_unavailable_message("No fresh AVP pose or ZED IMU data available for tracking sync."))
                return

            self.lbl_robot_yaw.setText("0.0°")
            self.lbl_robot_pitch.setText("0.0°")
            self.motor_initialized = True
            self.pose_initialized = True
            self._set_tracking_active(True)
            self._emit_runtime_event("info", "[TRACK] TRACKING_ACTIVE")

        def on_failure(message):
            self._set_tracking_active(False)
            self._warn("Warning", f"Failed to move motors to home safely: {message}")

        return self._start_homing_to_tracking_start(on_success=on_success, on_failure=on_failure)

    def toggle_tracking(self, checked):
        if checked:
            self.start_tracking_sequence()
        else:
            if self.is_tracking or self.is_tracking_paused:
                self._emit_runtime_event("info", "[TRACK] STOPPED")
            if self._homing_active:
                self._cancel_homing()
            self._set_tracking_active(False)

    def control_loop(self):
        if not self.avp_client:
            return

        self._sync_runtime_retargeter()
        sample = self._get_latest_head_pose_sample()
        was_paused = bool(self.is_tracking_paused)
        pose_status = self._get_pose_status()
        if was_paused and sample is not None and getattr(sample, "fresh", True) is not False:
            self._emit_runtime_event("info", f"[TRACK] RESYNC_BEGIN reason={self._last_pause_reason or 'unknown'}")
        if sample is not None and getattr(sample, "fresh", True) is not False:
            pose_data = sample.head_pose_matrix
            base_imu = sample.base_imu_rpy
            yaw_target, pitch_target = self.retargeter.compute_neck_target(pose_data, base_imu_rpy=base_imu)
            self.lbl_head_yaw.setText(f"{np.rad2deg(yaw_target):.1f}°")
            self.lbl_head_pitch.setText(f"{np.rad2deg(pitch_target):.1f}°")
        elif not self.is_tracking:
            return

        if self.is_tracking and self.motor_controller:
            motor_positions = self._get_present_positions()
            if motor_positions is None:
                self._emit_runtime_event("error", f"[MOTOR] PRESENT_POS_READ_FAIL reason={self._motor_unavailable_message()}")
                self._set_tracking_active(False)
                return

            tick_now = sample.timestamp if sample is not None and sample.timestamp is not None else time.monotonic()
            if self.runtime and not self.runtime.controller.robot_synced and not self.runtime.fault_latched:
                self.runtime.request_start_tracking()
            result = self.runtime.tick(
                sample=sample,
                motor_positions=motor_positions,
                now=tick_now,
            )
            if result.state is ControlState.TRACKING and result.reason == "auto_synced":
                result = self.runtime.tick(
                    sample=sample,
                    motor_positions=motor_positions,
                    now=tick_now,
                )
            runtime_status = self._update_tracking_pause_state()
            if runtime_status and runtime_status.fault_latched:
                self._emit_runtime_event("error", f"[TRACK] FAULT reason={runtime_status.reason or 'fault_latched'}")
                self._set_tracking_active(False)
                return
            if result.state is ControlState.HOLD:
                if not was_paused and runtime_status and runtime_status.tracking_paused:
                    reason = str(result.reason or runtime_status.reason or pose_status.get("reason") or "unknown")
                    fresh_flag = getattr(sample, "fresh", pose_status.get("fresh", False)) if sample is not None else pose_status.get("fresh", False)
                    self._last_pause_reason = reason
                    self._emit_runtime_event("warning", f"[AVP] POSE_INVALID reason={reason} fresh={'true' if fresh_flag else 'false'}")
                    self._emit_runtime_event(
                        "warning",
                        f"[TRACK] PAUSED reason={reason} hold={self._format_hold_commands(result.commands)}",
                    )
                if result.commands:
                    self._send_motor_commands(result.commands)
                return
            if result.state is not ControlState.TRACKING:
                return

            motor_commands = result.commands

            clamped_yaw_deg = np.rad2deg((motor_commands[config.YAW_MOTOR_ID] - config.ZERO_POS) * (2 * np.pi / config.STEPS_PER_REV))
            clamped_pitch_deg = np.rad2deg((motor_commands[config.PITCH_MOTOR_ID] - config.ZERO_POS) * (2 * np.pi / config.STEPS_PER_REV))
            self.lbl_robot_yaw.setText(f"{clamped_yaw_deg:.1f}°")
            self.lbl_robot_pitch.setText(f"{clamped_pitch_deg:.1f}°")
            self._send_motor_commands(motor_commands)
            if was_paused:
                self._emit_runtime_event("info", "[TRACK] RESUMED reason=auto_synced")
                self._last_pause_reason = ""
            self.is_tracking_paused = False

    def calibrate(self):
        """
        Initial Calibration Workflow:
        1. Stop Tracking
        2. Move Motors to Home (Physical Center)
        3. Prompt User to Align AVP & Camera
        4. Capture Offsets using ZED SDK & AVP Data
        5. Resume Tracking
        """
        # 1. Stop Tracking
        if self.is_tracking:
            self._set_tracking_active(False)
        self._sync_runtime_retargeter()
        if self.runtime:
            self.runtime.update_tracking_start_positions(self._tracking_start_positions())

        def continue_calibration():
            msg = QMessageBox()
            msg.setWindowTitle("初始化校准")
            msg.setText("<b>步骤 1：机器人回中</b><br>电机已移动到设定中心位。<br><br>"
                       "<b>步骤 2：对齐视角</b><br>请保持正视前方，并确认 ZED 相机处于水平。<br><br>"
                       "点击 <b>确定</b> 捕获当前零位。")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)

            if msg.exec() == QMessageBox.StandardButton.Ok:
                motor_positions = self._get_present_positions()
                sample = self._get_latest_head_pose_sample()
                result = None
                if motor_positions is not None and self.runtime:
                    tick_now = sample.timestamp if sample is not None and sample.timestamp is not None else time.monotonic()
                    self.runtime.request_start_tracking()
                    result = self.runtime.tick(sample=sample, motor_positions=motor_positions, now=tick_now)
                if result is None or result.state is not ControlState.TRACKING:
                    QMessageBox.warning(self, "警告", self._build_pose_unavailable_message("当前没有可用的 AVP 头部姿态数据，未能完成校准同步。"))
                    return

                self.motor_initialized = True
                self.pose_initialized = True
                self._set_tracking_active(True)
                QMessageBox.information(self, "完成", "校准完成，已开始跟踪。")

        if self._motor_motion_ready():
            def on_success(_positions):
                self.lbl_robot_yaw.setText("0.0°")
                self.lbl_robot_pitch.setText("0.0°")
                continue_calibration()

            def on_failure(_message):
                QMessageBox.warning(self, "警告", "电机未能安全回到中心位。")

            return self._start_homing_to_tracking_start(on_success=on_success, on_failure=on_failure)
        else:
            QMessageBox.warning(self, "警告", f"{self._motor_unavailable_message()} 本次校准只会影响软件偏移。")
            continue_calibration()
            return True
    
    def reset_calibration(self):
        if hasattr(self.retargeter, "request_resync"):
            self.retargeter.request_resync()
        else:
            self.retargeter.reset_calibration()
        if self.runtime:
            self.runtime.request_resync(auto_track=False)
            self.runtime.controller.robot_synced = False
        self.pose_initialized = False
