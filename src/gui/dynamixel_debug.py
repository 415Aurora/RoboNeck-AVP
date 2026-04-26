import sys
import time
from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QComboBox, QPushButton, QLineEdit, QSlider, QMessageBox, QTextBrowser,
    QCheckBox, QSpinBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor

from config import config
from src.core.motor_limits import (
    clamp_step_target,
    motor_limit_store as build_motor_limit_store,
    pose_limit_violation,
    tracking_start_pose_store as build_tracking_start_pose_store,
    validate_motor_limits,
)
from src.hardware.motor import MotorController
from src.hardware.mock_motor import MockMotorController


def motor_limit_store():
    return build_motor_limit_store()


def tracking_start_pose_store():
    return build_tracking_start_pose_store()

class DxlDebugWidget(QWidget):
    """
    Widget for debugging Dynamixel Motors (Connect, Monitor, Control, Param Tuning).
    """
    motor_connected = pyqtSignal(object) # Emits MotorController instance or None
    motor_limits_updated = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.motor_controller = None
        self.monitoring = False
        self.mock_mode = False
        self._last_reported_motor_state = None
        self._monitor_success_ticks = 0
        self._monitor_failure_ticks = 0
        self._motor_limit_store = motor_limit_store()
        self._tracking_start_store = tracking_start_pose_store()
        self._motor_limits = validate_motor_limits(self._motor_limit_store.load())
        
        self.init_ui()
        
        # Monitor Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.setInterval(50) # 50ms polling

    def init_ui(self):
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # 1. Connection Group
        grp_conn = QGroupBox("连接")
        layout_conn = QHBoxLayout()
        grp_conn.setLayout(layout_conn)
        
        layout_conn.addWidget(QLabel("端口："))
        self.combo_port = QComboBox()
        self.combo_port.addItems([config.DYNAMIXEL_PORT, "/dev/ttyUSB1", "COM3"])
        self.combo_port.setEditable(True)
        layout_conn.addWidget(self.combo_port)
        
        layout_conn.addWidget(QLabel("波特率："))
        self.combo_baud = QComboBox()
        self.combo_baud.addItems([str(config.BAUDRATE), "115200", "1000000", "57600"])
        layout_conn.addWidget(self.combo_baud)

        self.btn_connect = QPushButton("连接")
        self.btn_connect.setCheckable(True)
        self.btn_connect.clicked.connect(self.toggle_connection)
        self.btn_connect.setStyleSheet("background-color: #e74c3c; color: white;") # Start Red (Disconnected)
        layout_conn.addWidget(self.btn_connect)
        
        main_layout.addWidget(grp_conn)

        # 2. Status Monitor Group
        grp_status = QGroupBox("电机状态监视")
        layout_status = QGridLayout()
        grp_status.setLayout(layout_status)
        
        # Header
        layout_status.addWidget(QLabel("<b>参数</b>"), 0, 0)
        layout_status.addWidget(QLabel(f"<b>ID {config.YAW_MOTOR_ID}（偏航）</b>"), 0, 1)
        layout_status.addWidget(QLabel(f"<b>ID {config.PITCH_MOTOR_ID}（俯仰）</b>"), 0, 2)
        
        # Rows: Position, Velocity, Current, Voltage, Temp
        self.labels_status = {}
        params = ["位置（度）", "速度（RPM）", "电流（mA）", "电压（V）", "温度（°C）"]
        for i, param in enumerate(params):
            row = i + 1
            layout_status.addWidget(QLabel(param), row, 0)
            
            lbl_yaw = QLineEdit("N/A")
            lbl_yaw.setReadOnly(True)
            lbl_pitch = QLineEdit("N/A")
            lbl_pitch.setReadOnly(True)
            
            layout_status.addWidget(lbl_yaw, row, 1)
            layout_status.addWidget(lbl_pitch, row, 2)
            
            self.labels_status[f"YAW_{i}"] = lbl_yaw
            self.labels_status[f"PITCH_{i}"] = lbl_pitch
            
        main_layout.addWidget(grp_status)

        # 3. Manual Control Group
        grp_control = QGroupBox("手动控制")
        layout_control = QGridLayout()
        grp_control.setLayout(layout_control)
        
        # Jog Buttons
        btn_left = QPushButton("左转（偏航+）")
        btn_right = QPushButton("右转（偏航-）")
        btn_up = QPushButton("上抬（俯仰-）")
        btn_down = QPushButton("下压（俯仰+）")
        
        # Wiring Jog
        btn_left.clicked.connect(lambda: self.jog(config.YAW_MOTOR_ID, 1))
        btn_right.clicked.connect(lambda: self.jog(config.YAW_MOTOR_ID, -1))
        btn_up.clicked.connect(lambda: self.jog(config.PITCH_MOTOR_ID, -1)) # Pitch direction depends on install
        btn_down.clicked.connect(lambda: self.jog(config.PITCH_MOTOR_ID, 1))

        layout_control.addWidget(btn_left, 0, 0)
        layout_control.addWidget(btn_right, 0, 1)
        layout_control.addWidget(btn_up, 1, 0)
        layout_control.addWidget(btn_down, 1, 1)

        # Torque Switch
        self.chk_torque = QCheckBox("使能扭矩")
        # Wiring Torque
        self.chk_torque.toggled.connect(self.on_torque_toggled)
        layout_control.addWidget(self.chk_torque, 0, 2, 1, 2)

        # Step Size
        layout_control.addWidget(QLabel("步长："), 1, 2)
        self.combo_step = QComboBox()
        self.combo_step.addItems(["1 度", "5 度", "10 度"])
        layout_control.addWidget(self.combo_step, 1, 3, 1, 2)
        
        # Absolute Move
        layout_control.addWidget(QLabel("目标角度："), 2, 0)
        self.input_goal = QLineEdit("0")
        layout_control.addWidget(self.input_goal, 2, 1)
        self.btn_go = QPushButton("执行")
        self.btn_go.clicked.connect(self.on_btn_go)
        layout_control.addWidget(self.btn_go, 2, 2)
        
        # Speed Slider
        layout_control.addWidget(QLabel("速度（RPM）："), 3, 0)
        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(0, 100)
        self.slider_speed.setValue(20) # Safe default
        self.slider_speed.sliderReleased.connect(self.update_motor_params)
        layout_control.addWidget(self.slider_speed, 3, 1, 1, 3)
        self.lbl_speed = QLabel("20 RPM")
        self.slider_speed.valueChanged.connect(lambda v: self.lbl_speed.setText(f"{v} RPM"))
        layout_control.addWidget(self.lbl_speed, 3, 4)

        main_layout.addWidget(grp_control)

        # 4. Step Limits
        grp_limits = QGroupBox("电机限位")
        layout_limits = QGridLayout()
        grp_limits.setLayout(layout_limits)

        btn_prepare_limits = QPushButton("释放舵机设置限位")
        btn_prepare_limits.clicked.connect(self.begin_motor_limit_adjustment)
        layout_limits.addWidget(btn_prepare_limits, 0, 0, 1, 2)

        self._limit_spins = {}
        limit_rows = [
            ("yaw", "偏航最小步进", "min", 1),
            ("yaw", "偏航最大步进", "max", 2),
            ("pitch", "俯仰最小步进", "min", 3),
            ("pitch", "俯仰最大步进", "max", 4),
        ]
        for axis, label_text, bound, row in limit_rows:
            layout_limits.addWidget(QLabel(f"{label_text}："), row, 0)
            spin = QSpinBox()
            spin.setRange(0, config.STEPS_PER_REV - 1)
            layout_limits.addWidget(spin, row, 1)
            button = QPushButton("读取当前值")
            button.clicked.connect(lambda _checked=False, a=axis, b=bound: self.read_current_limit(a, b))
            layout_limits.addWidget(button, row, 2)
            self._limit_spins[(axis, bound)] = spin

        self.spin_yaw_min = self._limit_spins[("yaw", "min")]
        self.spin_yaw_max = self._limit_spins[("yaw", "max")]
        self.spin_pitch_min = self._limit_spins[("pitch", "min")]
        self.spin_pitch_max = self._limit_spins[("pitch", "max")]

        btn_save_limits = QPushButton("保存限位")
        btn_save_limits.clicked.connect(self.save_motor_limits)
        layout_limits.addWidget(btn_save_limits, 5, 0, 1, 3)
        main_layout.addWidget(grp_limits)

        self._load_motor_limits()

        # 5. Param Tuning (PID + Torque Limit)
        grp_param = QGroupBox("参数调节")
        layout_param = QGridLayout()
        grp_param.setLayout(layout_param)
        
        # PID Sliders
        self.pid_sliders = {}
        for i, val in enumerate(["P", "I", "D"]):
            layout_param.addWidget(QLabel(f"{val} 增益："), i, 0)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 2000)
            if val == "P": slider.setValue(600)
            elif val == "I": slider.setValue(50)
            elif val == "D": slider.setValue(50)
            slider.sliderReleased.connect(self.update_motor_params)
            layout_param.addWidget(slider, i, 1)
            lbl = QLabel(str(slider.value()))
            slider.valueChanged.connect(lambda v, l=lbl: l.setText(str(v)))
            layout_param.addWidget(lbl, i, 2)
            self.pid_sliders[val] = slider

        # Torque Limit
        layout_param.addWidget(QLabel("扭矩限制（%）："), 3, 0)
        self.slider_torque = QSlider(Qt.Orientation.Horizontal)
        self.slider_torque.setRange(0, 100)
        self.slider_torque.setValue(100)
        self.slider_torque.sliderReleased.connect(self.update_motor_params)
        layout_param.addWidget(self.slider_torque, 3, 1)
        self.lbl_torque = QLabel("100%")
        self.slider_torque.valueChanged.connect(lambda v: self.lbl_torque.setText(f"{v}%"))
        layout_param.addWidget(self.lbl_torque, 3, 2)

        main_layout.addWidget(grp_param)

        # 6. Reset / Alarm
        grp_reset = QGroupBox("系统与告警")
        layout_reset = QHBoxLayout()
        grp_reset.setLayout(layout_reset)
        
        self.btn_reset_zero = QPushButton("回零")
        self.btn_reset_zero.setStyleSheet("background-color: #e67e22; color: white;")
        self.btn_reset_zero.clicked.connect(self.on_reset_zero)
        
        self.btn_reboot = QPushButton("重启电机")
        self.btn_reboot.setStyleSheet("background-color: #c0392b; color: white;")
        self.btn_reboot.clicked.connect(self.on_reboot)

        layout_reset.addWidget(self.btn_reset_zero)
        layout_reset.addWidget(self.btn_reboot)
        
        self.txt_alarm = QTextBrowser()
        self.txt_alarm.setMaximumHeight(60)
        layout_reset.addWidget(self.txt_alarm)
        
        main_layout.addWidget(grp_reset)

        self.apply_styles()

    def apply_styles(self):
        # Additional specific styles if needed
        pass

    def get_motor_limits(self):
        return dict(self._motor_limits)

    def _load_motor_limits(self):
        self._motor_limits = validate_motor_limits(self._motor_limit_store.load())
        self.spin_yaw_min.setValue(self._motor_limits["yaw_min_step"])
        self.spin_yaw_max.setValue(self._motor_limits["yaw_max_step"])
        self.spin_pitch_min.setValue(self._motor_limits["pitch_min_step"])
        self.spin_pitch_max.setValue(self._motor_limits["pitch_max_step"])

    def _current_limit_values(self):
        return {
            "yaw_min_step": int(self.spin_yaw_min.value()),
            "yaw_max_step": int(self.spin_yaw_max.value()),
            "pitch_min_step": int(self.spin_pitch_min.value()),
            "pitch_max_step": int(self.spin_pitch_max.value()),
        }

    def _set_torque_checkbox(self, checked):
        if not hasattr(self.chk_torque, "setChecked"):
            return

        if hasattr(self.chk_torque, "blockSignals"):
            previous = self.chk_torque.blockSignals(True)
            self.chk_torque.setChecked(checked)
            self.chk_torque.blockSignals(previous)
            return

        self.chk_torque.setChecked(checked)

    def _set_all_motor_torque(self, enabled):
        if not self._controller_motion_ready():
            return False

        self.motor_controller.enable_torque(config.YAW_MOTOR_ID, enabled)
        self.motor_controller.enable_torque(config.PITCH_MOTOR_ID, enabled)
        self._set_torque_checkbox(enabled)
        return True

    def _motor_unavailable_message(self):
        if not self.motor_controller or not getattr(self.motor_controller, "connected", False):
            return "电机未连接。"
        reason = getattr(self.motor_controller, "motor_error", "")
        if reason:
            return f"电机未就绪：{reason}"
        return "电机未就绪，请检查电机供电、接线、ID 和波特率。"

    def begin_motor_limit_adjustment(self):
        if not self._controller_motion_ready():
            QMessageBox.warning(self, "警告", f"{self._motor_unavailable_message()} 无法进入限位设置模式。")
            return False

        self._set_all_motor_torque(False)
        self.txt_alarm.append("Torque Disabled for motor limit adjustment.")
        return True

    def read_current_limit(self, axis, bound):
        if not self.begin_motor_limit_adjustment():
            return False

        motor_id = config.YAW_MOTOR_ID if axis == "yaw" else config.PITCH_MOTOR_ID
        current = self.motor_controller.get_present_position(motor_id)
        if current is None:
            QMessageBox.warning(self, "警告", "读取当前位置失败。")
            return False

        self._limit_spins[(axis, bound)].setValue(int(current))
        return True

    def save_motor_limits(self):
        try:
            limits = validate_motor_limits(self._current_limit_values())
        except ValueError as exc:
            QMessageBox.warning(self, "警告", str(exc))
            return False

        tracking_start = self._tracking_start_store.load()
        warning = pose_limit_violation(
            limits,
            tracking_start["yaw_start_step"],
            tracking_start["pitch_start_step"],
            pose_name="已保存的跟踪初始位",
        )
        if warning:
            QMessageBox.warning(self, "警告", warning)
            return False

        saved = self._motor_limit_store.save(
            limits["yaw_min_step"],
            limits["yaw_max_step"],
            limits["pitch_min_step"],
            limits["pitch_max_step"],
        )
        self._motor_limits = dict(saved)
        self.motor_limits_updated.emit(dict(saved))
        self.txt_alarm.append(f"Motor limits saved: {saved}")
        QMessageBox.information(self, "完成", "电机限位已保存。")
        return True

    def _clamp_motor_target(self, motor_id, target_step):
        axis = "yaw" if motor_id == config.YAW_MOTOR_ID else "pitch"
        return clamp_step_target(self._motor_limits, axis, target_step)

    def _controller_motion_ready(self):
        return bool(
            self.motor_controller
            and getattr(self.motor_controller, "connected", False)
            and getattr(self.motor_controller, "motors_ready", True)
        )

    def _motor_state_signature(self):
        if not self.motor_controller:
            return None
        return (
            bool(getattr(self.motor_controller, "connected", False)),
            bool(getattr(self.motor_controller, "motors_ready", True)),
            str(getattr(self.motor_controller, "motor_error", "") or ""),
        )

    def _emit_motor_state_if_changed(self, force=False):
        state = self._motor_state_signature()
        if not force and state == self._last_reported_motor_state:
            return False
        self._last_reported_motor_state = state
        self.motor_connected.emit(self.motor_controller if state and state[0] else None)
        return True

    def _ready_fail_ticks_threshold(self):
        return int(max(1, getattr(config, "GUI_MOTOR_READY_FAIL_TICKS", 3)))

    def _ready_recover_ticks_threshold(self):
        return int(max(1, getattr(config, "GUI_MOTOR_READY_RECOVER_TICKS", 2)))

    def _format_probe_report(self, probe):
        parts = [f"Probe ID {probe.get('motor_id', '?')}"]
        if probe.get("model_number") is not None:
            parts.append(f"model={probe['model_number']}")
        if probe.get("present_position") is not None:
            parts.append(f"present_position={probe['present_position']}")
        if probe.get("failed_stage"):
            parts.append(f"failed_stage={probe['failed_stage']}")
        if probe.get("sdk_error"):
            parts.append(f"sdk_error={probe['sdk_error']}")
        return " | ".join(parts)

    def _append_probe_diagnostics(self, motor_ids):
        if not self.motor_controller or not hasattr(self.motor_controller, "probe_motor"):
            return False

        appended = False
        for motor_id in motor_ids:
            try:
                probe = self.motor_controller.probe_motor(motor_id)
            except Exception as exc:
                self.txt_alarm.append(f"Probe ID {motor_id} failed: {exc}")
                appended = True
                continue

            if not probe:
                continue

            if probe.get("failed_stage") or probe.get("sdk_error"):
                self.txt_alarm.append(self._format_probe_report(probe))
                appended = True
        return appended

    def _validate_motion_controller(self):
        if not self.motor_controller or not getattr(self.motor_controller, "connected", False):
            return False

        if hasattr(self.motor_controller, "validate_motors"):
            return bool(
                self.motor_controller.validate_motors(
                    (config.YAW_MOTOR_ID, config.PITCH_MOTOR_ID),
                    retries=5,
                    initial_delay_sec=0.2,
                    retry_delay_sec=0.1,
                )
            )

        yaw_position = self.motor_controller.get_present_position(config.YAW_MOTOR_ID)
        pitch_position = self.motor_controller.get_present_position(config.PITCH_MOTOR_ID)
        ready = yaw_position is not None and pitch_position is not None
        if hasattr(self.motor_controller, "set_motor_readiness"):
            error = "" if ready else "无法读取配置电机的当前位置。"
            self.motor_controller.set_motor_readiness(ready, error)
        return ready

    def toggle_connection(self):
        if self.btn_connect.isChecked():
            # Connect
            port = self.combo_port.currentText()
            baud = int(self.combo_baud.currentText())
            try:
                if config.MOCK_MOTORS:
                    self.motor_controller = MockMotorController(port, baud)
                    self.txt_alarm.append("Connected to MOCK Motor Controller.")
                else:
                    self.motor_controller = MotorController(port, baud)
                
                if self.motor_controller.connected:
                    self.btn_connect.setText("Disconnect")
                    self.btn_connect.setStyleSheet("background-color: #2ecc71; color: white;")
                    self.txt_alarm.append("Connected successfully.")
                    self.start_monitoring()
                    self._monitor_success_ticks = 0
                    self._monitor_failure_ticks = 0

                    if self._validate_motion_controller():
                        safe_vel = int(getattr(config, "TRACKING_PROFILE_VELOCITY", 0))
                        safe_acc = int(getattr(config, "TRACKING_PROFILE_ACCELERATION", 80))
                        self.motor_controller.set_profile(config.YAW_MOTOR_ID, safe_vel, safe_acc)
                        self.motor_controller.set_profile(config.PITCH_MOTOR_ID, safe_vel, safe_acc)
                        self.motor_controller.set_pid(config.YAW_MOTOR_ID, 600, 50, 50)
                        self.motor_controller.set_pid(config.PITCH_MOTOR_ID, 600, 50, 50)
                        self.txt_alarm.append(f"Safety Profile (Acc={safe_acc}) & PID (600/50/50) Applied")
                        self.chk_torque.setChecked(True)
                        self._emit_motor_state_if_changed()
                    else:
                        reason = getattr(self.motor_controller, "motor_error", "") or "配置电机未就绪。"
                        self.txt_alarm.append(f"Motor connection is up, but motion is disabled: {reason}")
                        self._append_probe_diagnostics((config.YAW_MOTOR_ID, config.PITCH_MOTOR_ID))
                        self._emit_motor_state_if_changed()
                        QMessageBox.warning(self, "警告", f"串口已连接，但电机未就绪：{reason}")
                    
                else:
                    self.btn_connect.setChecked(False)
                    self.txt_alarm.append("Failed to connect (SDK Error).")
                    
            except Exception as e:
                self.btn_connect.setChecked(False)
                self.txt_alarm.append(f"Connection Exception: {e}")
        else:
            # Disconnect
            self.monitoring = False
            self.timer.stop()
            self._monitor_success_ticks = 0
            self._monitor_failure_ticks = 0
            
            # Auto Disable Torque
            if self.motor_controller:
                try:
                    if self._set_all_motor_torque(False):
                        self.txt_alarm.append("Torque Disabled before disconnect.")
                    else:
                        self.txt_alarm.append("Skipped torque disable before disconnect because motors are not ready.")
                except:
                    pass
                self.motor_controller.close()
                self.motor_controller = None
            
            self.chk_torque.setChecked(False) # Reset UI
            self._emit_motor_state_if_changed(force=True) # Notify disconnection
            self.btn_connect.setText("Connect")
            self.btn_connect.setStyleSheet("background-color: #e74c3c; color: white;")
            self.txt_alarm.append("Disconnected.")

    def start_monitoring(self):
        """Start status polling if connected."""
        if not self.motor_controller or not getattr(self.motor_controller, "connected", False):
            self.monitoring = False
            self.timer.stop()
            return False

        self.monitoring = True
        if not self.timer.isActive():
            self.timer.start()
        return True

    def stop_monitoring(self):
        """Stop status polling."""
        self.monitoring = False
        self.timer.stop()

    def update_status(self):
        if not self.motor_controller:
            return

        currently_ready = bool(getattr(self.motor_controller, "motors_ready", True))
        all_status_ok = True
        failure_reason = ""
        failed_motor_id = None
        for mid, prefix in [(config.YAW_MOTOR_ID, "YAW"), (config.PITCH_MOTOR_ID, "PITCH")]:
            status = None
            status_error = ""
            if hasattr(self.motor_controller, "read_detailed_status_with_error"):
                status, status_error = self.motor_controller.read_detailed_status_with_error(mid)
            else:
                status = self.motor_controller.read_detailed_status(mid)
            if status:
                # 0: Position
                steps = status['position']
                # Convert steps to degrees (approx) relative to zero
                # 0-4096 => 0-360. Zero at 2048.
                deg = (steps - 2048) * (360.0 / 4096.0)
                self.labels_status[f"{prefix}_0"].setText(f"{deg:.1f}° ({steps})")
                
                # 1: Velocity
                self.labels_status[f"{prefix}_1"].setText(f"{status['velocity']:.1f}")
                
                # 2: Current
                self.labels_status[f"{prefix}_2"].setText(f"{status['current']:.0f}")
                
                # 3: Voltage
                self.labels_status[f"{prefix}_3"].setText(f"{status['voltage']:.1f}")
                
                # 4: Temp
                temp = status['temperature']
                lbl_temp = self.labels_status[f"{prefix}_4"]
                lbl_temp.setText(f"{temp} °C")
                if temp > 60:
                    lbl_temp.setStyleSheet("background-color: red; color: white;")
                else:
                    lbl_temp.setStyleSheet("")
            else:
                all_status_ok = False
                if not failure_reason:
                    failure_reason = status_error or f"无法读取电机 ID {mid} 的状态。"
                    failed_motor_id = mid

        if hasattr(self.motor_controller, "set_motor_readiness"):
            if all_status_ok:
                self._monitor_failure_ticks = 0
                if currently_ready:
                    self._monitor_success_ticks = self._ready_recover_ticks_threshold()
                else:
                    self._monitor_success_ticks += 1
                    if self._monitor_success_ticks >= self._ready_recover_ticks_threshold():
                        self.motor_controller.set_motor_readiness(True, "")
                        self._monitor_success_ticks = self._ready_recover_ticks_threshold()
            else:
                self._monitor_success_ticks = 0
                if currently_ready:
                    self._monitor_failure_ticks += 1
                    if self._monitor_failure_ticks >= self._ready_fail_ticks_threshold():
                        self.motor_controller.set_motor_readiness(False, failure_reason)
                        if failed_motor_id is not None:
                            self._append_probe_diagnostics((failed_motor_id,))
                        self._monitor_failure_ticks = self._ready_fail_ticks_threshold()
                else:
                    self._monitor_failure_ticks = min(
                        self._ready_fail_ticks_threshold(),
                        self._monitor_failure_ticks + 1,
                    )
            if self._last_reported_motor_state is None:
                self._last_reported_motor_state = self._motor_state_signature()
            else:
                self._emit_motor_state_if_changed()
    
    def jog(self, motor_id, direction):
        if not self._controller_motion_ready():
            return
        step_text = self.combo_step.currentText()
        step_deg = int(step_text.split(' ')[0])
        
        current_pos = self.motor_controller.get_present_position(motor_id)
        if current_pos is None: return
        
        # Convert deg to steps
        step_delta = int(step_deg * (4096.0 / 360.0)) * direction
        target_pos = self._clamp_motor_target(motor_id, current_pos + step_delta)
        
        self.motor_controller.set_goal_positions({motor_id: target_pos})
        self.txt_alarm.append(f"Jog ID {motor_id} to {target_pos}")

    def on_btn_go(self):
        if not self._controller_motion_ready():
            return
        try:
            val = float(self.input_goal.text())
            # Clamp
            if val < -90: val = -90
            if val > 90: val = 90
            
            # Convert to steps
            # 2048 + deg * (4096/360)
            target_yaw = self._clamp_motor_target(
                config.YAW_MOTOR_ID,
                2048 + (val * 4096.0 / 360.0),
            )
            
            # Smart move: only move checked/selected? 
            # For now move Yaw to target
            self.motor_controller.set_goal_positions({
                config.YAW_MOTOR_ID: int(target_yaw)
            })
            self.txt_alarm.append(f"Moving One to {val} deg")
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid Angle")

    def update_motor_params(self):
        if not self._controller_motion_ready():
            return
        
        # PID
        p = self.pid_sliders["P"].value()
        i = self.pid_sliders["I"].value()
        d = self.pid_sliders["D"].value()
        
        self.motor_controller.set_pid(config.YAW_MOTOR_ID, p, i, d)
        self.motor_controller.set_pid(config.PITCH_MOTOR_ID, p, i, d)
        
        # Torque Limit
        limit = self.slider_torque.value()
        # Map 0-100% to 0-885 (Goal PWM limit usually around 885 max for X series)
        pwm_limit = int(limit * 885 / 100)
        self.motor_controller.set_goal_pwm(config.YAW_MOTOR_ID, pwm_limit)
        self.motor_controller.set_goal_pwm(config.PITCH_MOTOR_ID, pwm_limit)
        
        # Speed Profile
        rpm = self.slider_speed.value()
        # Convert RPM to internal unit? 
        # Unit is 0.229 RPM. 
        vel_unit = int(rpm / 0.229)
        # Use safer acceleration (e.g. 50) instead of 200
        acc_val = 50 
        self.motor_controller.set_profile(config.YAW_MOTOR_ID, vel_unit, acc_val)
        self.motor_controller.set_profile(config.PITCH_MOTOR_ID, vel_unit, acc_val)
        
        self.txt_alarm.append(f"Params Updated: PID={p}/{i}/{d}, Speed={rpm}rpm")

    def on_reset_zero(self):
        if not self._controller_motion_ready():
            return
        self.motor_controller.set_goal_positions({
            config.YAW_MOTOR_ID: self._clamp_motor_target(config.YAW_MOTOR_ID, 2048),
            config.PITCH_MOTOR_ID: self._clamp_motor_target(config.PITCH_MOTOR_ID, 2048),
        })
        self.txt_alarm.append("Zero Reset Triggered.")

    def on_reboot(self):
        if not self.motor_controller: return
        self.motor_controller.reboot(config.YAW_MOTOR_ID)
        self.motor_controller.reboot(config.PITCH_MOTOR_ID)
        self.txt_alarm.append("Reboot Command Sent.")

    def on_torque_toggled(self, checked):
        if not self._controller_motion_ready():
            return
        self.motor_controller.enable_torque(config.YAW_MOTOR_ID, checked)
        self.motor_controller.enable_torque(config.PITCH_MOTOR_ID, checked)
        
        state = "Enabled" if checked else "Disabled"
        self.txt_alarm.append(f"Torque {state}.")

    def clean_shutdown(self):
        """Safely shut down: Stop Monitoring -> Disable Torque -> Close Port."""
        self.monitoring = False
        self.timer.stop() # CRITICAL: Stop timer before closing port
        
        if self.motor_controller and self.motor_controller.connected:
            try:
                # Auto Disable Torque (User Request)
                self.motor_controller.enable_torque(config.YAW_MOTOR_ID, False)
                self.motor_controller.enable_torque(config.PITCH_MOTOR_ID, False)
                print("[DxlDebug] Torque Disabled on Shutdown.")
            except Exception as e:
                print(f"[DxlDebug] Error disabling torque on shutdown: {e}")
            
            self.motor_controller.close()
            self.motor_controller = None
            print("[DxlDebug] Port Closed.")
