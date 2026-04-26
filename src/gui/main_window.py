import json
import time

import cv2
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from config import config
from src.core.avp_connection import load_avp_connection_settings, save_avp_connection_settings
from src.core.camera_controller import CameraController
from src.core.client import AVPClient
from src.core.mock_client import MockAVPClient
from src.gui.camera_panel_logic import precheck_rtp_stream_request
from src.gui.camera_param import CameraParamWidget
from src.gui.camera_stream import CameraStreamPage
from src.gui.dashboard import DashboardWidget
from src.gui.diagnostics import DiagnosticsWidget
from src.gui.dynamixel_debug import DxlDebugWidget
from src.gui.motor_calibration import MotorCalibrationPage
from src.gui.pose_control import PoseControlWidget
from src.gui.teleop_stream import TeleopStreamWidget
from src.gui.ui_state import SystemSnapshot


def _current_utc_timestamp():
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())


class MainWindow(QMainWindow):
    """
    Main operator console with dashboard-first workflow.
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("RobotNeck-AVP Control Center")
        self.resize(1200, 850)

        self.client = None
        self.camera_controller = CameraController()
        self.motor_controller = None
        self.last_camera_diag_update = 0.0
        self._last_warning_message = ""

        self.init_ui()
        self.apply_styles()
        self._load_avp_settings()
        self.propagate_dependencies()
        self.refresh_camera_diagnostics(force=True)
        self.refresh_system_snapshot()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_loop)
        self.timer.start(33)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.pose_widget = PoseControlWidget()
        self.camera_widget = CameraParamWidget()
        self.teleop_widget = TeleopStreamWidget()
        self.dxl_debug = DxlDebugWidget()
        self.dashboard_widget = DashboardWidget()
        self.camera_page = CameraStreamPage(self.camera_widget, self.teleop_widget)
        self.motor_page = MotorCalibrationPage(self.pose_widget, self.dxl_debug)
        self.diagnostics_widget = DiagnosticsWidget()

        self.tabs.addTab(self.dashboard_widget, "主控台")
        self.tabs.addTab(self.camera_page, "相机与串流")
        self.tabs.addTab(self.motor_page, "电机与初始化")
        self.tabs.addTab(self.diagnostics_widget, "诊断与日志")

        self.tabs.currentChanged.connect(self.on_tab_changed)

        self.camera_widget.param_changed.connect(self.on_cam_param_changed)
        self.camera_widget.auto_exposure_toggled.connect(self.on_cam_auto_exp)
        self.camera_widget.auto_wb_toggled.connect(self.on_cam_auto_wb)
        self.camera_widget.confidence_changed.connect(self.on_cam_confidence)
        self.camera_widget.disparity_changed.connect(self.on_cam_disparity)
        self.camera_widget.capture_mode_changed.connect(self.on_cam_mode)
        self.camera_widget.focus_changed.connect(self.on_cam_focus)
        self.camera_widget.auto_focus_toggled.connect(self.on_cam_auto_focus)
        self.camera_widget.rtp_stream_requested.connect(self.on_rtp_stream_requested)
        if hasattr(self.camera_widget, "camera_connection_requested"):
            self.camera_widget.camera_connection_requested.connect(self.on_camera_connection_requested)

        self.teleop_widget.start_stream_requested.connect(self.start_stream)
        self.teleop_widget.stop_stream_requested.connect(self.stop_stream)
        self.teleop_widget.restart_stream_requested.connect(self.restart_stream)
        self.dxl_debug.motor_connected.connect(self.on_motor_connection_changed)

        if hasattr(self.pose_widget, "runtime_event"):
            self.pose_widget.runtime_event.connect(self.record_event)

        self.dashboard_widget.connect_motor_requested.connect(self.connect_motor_from_dashboard)
        self.dashboard_widget.check_avp_requested.connect(self.check_avp_from_dashboard)
        self.dashboard_widget.connect_avp_requested.connect(self.connect_avp_from_dashboard)
        self.dashboard_widget.disconnect_avp_requested.connect(self.disconnect_avp_from_dashboard)
        self.dashboard_widget.retry_avp_requested.connect(self.retry_avp_from_dashboard)
        self.dashboard_widget.connect_camera_requested.connect(self.connect_camera_from_dashboard)
        self.dashboard_widget.start_stream_requested.connect(self.start_stream_from_dashboard)
        self.dashboard_widget.motor_init_requested.connect(self.motor_init_from_dashboard)
        self.dashboard_widget.pose_init_requested.connect(self.pose_init_from_dashboard)
        self.dashboard_widget.start_tracking_requested.connect(self.start_tracking_from_dashboard)
        self.dashboard_widget.stop_tracking_requested.connect(self.stop_tracking_from_dashboard)
        self.dashboard_widget.safe_reset_requested.connect(self.safe_reset)
        self.dashboard_widget.open_camera_tools_requested.connect(lambda: self.tabs.setCurrentIndex(1))
        self.dashboard_widget.open_motor_tools_requested.connect(lambda: self.tabs.setCurrentIndex(2))
        self.dashboard_widget.open_diagnostics_requested.connect(lambda: self.tabs.setCurrentIndex(3))

        global_group = QWidget()
        global_layout = QHBoxLayout()
        global_group.setLayout(global_layout)

        self.btn_load = QPushButton("Load Config")
        self.btn_load.clicked.connect(self.load_config)
        self.btn_save = QPushButton("Save Config")
        self.btn_save.clicked.connect(self.save_config)
        self.btn_quit = QPushButton("Quit")
        self.btn_quit.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        self.btn_quit.clicked.connect(self.close)

        global_layout.addWidget(self.btn_load)
        global_layout.addWidget(self.btn_save)
        global_layout.addStretch()
        global_layout.addWidget(self.btn_quit)
        main_layout.addWidget(global_group)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.lbl_motor_status = QPushButton("Motors: Disconnected")
        self.lbl_motor_status.setFlat(True)
        self.lbl_motor_status.setStyleSheet("color: red; border: none; font-weight: bold;")

        self.lbl_cam_status = QPushButton("Camera: Disconnected")
        self.lbl_cam_status.setFlat(True)
        self.lbl_cam_status.setStyleSheet("color: red; border: none; font-weight: bold;")
        self.lbl_cam_status.clicked.connect(self.reconnect_camera)

        self.status_bar.addPermanentWidget(self.lbl_motor_status)
        self.status_bar.addPermanentWidget(self.lbl_cam_status)

    def apply_styles(self):
        style = """
        QMainWindow, QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
            font-family: "Segoe UI", "Roboto", Helvetica, Arial, sans-serif;
        }
        QTabWidget::pane {
            border: 1px solid #444;
            background: #333;
        }
        QTabBar::tab {
            background: #444;
            color: #aaa;
            padding: 8px 12px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background: #333;
            color: #fff;
            font-weight: bold;
            border-bottom: 2px solid #3498db;
        }
        QPushButton {
            background-color: #444;
            border: 1px solid #666;
            border-radius: 4px;
            padding: 5px;
            color: #eee;
        }
        QPushButton:hover {
            background-color: #555;
            border-color: #888;
        }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background-color: #222;
            color: #fff;
            border: 1px solid #555;
            padding: 4px;
            border-radius: 3px;
        }
        """
        self.setStyleSheet(style)

    def _load_avp_settings(self):
        settings = load_avp_connection_settings()
        if hasattr(self.dashboard_widget, "set_avp_settings"):
            self.dashboard_widget.set_avp_settings(
                ip=settings.get("ip", getattr(config, "AVP_IP", "")),
                auto_reconnect=settings.get("auto_reconnect", False),
            )

    def _create_client(self, ip):
        if config.MOCK_AVP:
            return MockAVPClient(ip)
        return AVPClient(ip)

    def on_client_ready(self, client):
        self.client = client
        self.propagate_dependencies()
        self.refresh_system_snapshot()

    def on_motor_connection_changed(self, controller):
        self.motor_controller = controller
        if controller:
            self.lbl_motor_status.setText("Motors: Connected")
            self.lbl_motor_status.setStyleSheet("color: #2ecc71; border: none; font-weight: bold;")
            ready = bool(getattr(controller, "motors_ready", getattr(controller, "connected", False)))
            if not ready:
                reason = getattr(controller, "motor_error", "") or "配置电机未就绪。"
                self.record_event("warning", f"串口已连接，但电机未就绪：{reason}")
        else:
            self.lbl_motor_status.setText("Motors: Disconnected")
            self.lbl_motor_status.setStyleSheet("color: red; border: none; font-weight: bold;")
        self.propagate_dependencies()
        self.refresh_system_snapshot()

    def propagate_dependencies(self):
        if hasattr(self.pose_widget, "set_dependencies"):
            self.pose_widget.set_dependencies(self.motor_controller, self.client, self.camera_controller)

    def _avp_connection_status(self):
        if self.client and hasattr(self.client, "get_connection_status"):
            return self.client.get_connection_status()
        if self.client:
            return {
                "state": "ready",
                "ip": getattr(self.client, "ip", ""),
                "auto_reconnect": False,
                "last_error": None,
                "state_age_sec": 0.0,
                "last_sample_timestamp": None,
                "has_ever_received_pose": True,
            }
        return {
            "state": "idle",
            "ip": "",
            "auto_reconnect": False,
            "last_error": None,
            "state_age_sec": 0.0,
            "last_sample_timestamp": None,
            "has_ever_received_pose": False,
        }

    def _avp_pose_status(self):
        if self.client and hasattr(self.client, "get_pose_status"):
            return self.client.get_pose_status()
        return {"valid": False, "reason": "idle", "fresh": False}

    def refresh_system_snapshot(self):
        connection_status = self._avp_connection_status()
        pose_status = self._avp_pose_status()
        avp_connected = connection_status.get("state") in {
            "connecting",
            "connected_waiting_first_sample",
            "ready",
            "reconnecting",
        }

        snapshot = SystemSnapshot(
            avp_connected=avp_connected,
            camera_connected=bool(self.camera_controller.is_connected),
            motor_connected=bool(self.motor_controller and getattr(self.motor_controller, "connected", False)),
            motor_ready=bool(self.motor_controller and getattr(self.motor_controller, "motors_ready", getattr(self.motor_controller, "connected", False))),
            motor_reason="" if not self.motor_controller else getattr(self.motor_controller, "motor_error", ""),
            streaming=bool(getattr(self.teleop_widget, "is_streaming", False)),
            tracking=bool(getattr(self.pose_widget, "is_tracking", False)),
            tracking_paused=bool(getattr(self.pose_widget, "is_tracking_paused", False)),
            motor_initialized=bool(getattr(self.pose_widget, "motor_initialized", False)),
            pose_initialized=bool(getattr(self.pose_widget, "pose_initialized", False)),
            pose_sample_valid=bool(pose_status.get("valid", False)),
            pose_sample_reason=pose_status.get("reason", ""),
            pose_sample_fresh=bool(pose_status.get("fresh", False)),
            last_warning=self._last_warning_message,
        )
        self.dashboard_widget.update_system_snapshot(snapshot)
        self.diagnostics_widget.update_system_snapshot(snapshot)
        if hasattr(self.dashboard_widget, "update_avp_runtime"):
            self.dashboard_widget.update_avp_runtime(connection_status)
        return snapshot

    def refresh_camera_diagnostics(self, force=False):
        now = time.time()
        if not force and now - self.last_camera_diag_update < 0.25:
            return
        self.last_camera_diag_update = now

        if hasattr(self.camera_widget, "update_runtime"):
            self.camera_widget.update_runtime(
                device_info=self.camera_controller.get_device_info(),
                sensor_snapshot=self.camera_controller.get_sensor_snapshot(),
                health_status=self.camera_controller.get_health_status(),
                streaming_status=self.camera_controller.get_streaming_status(),
            )

        if hasattr(self.camera_widget, "set_connected"):
            self.camera_widget.set_connected(self.camera_controller.is_connected)
        if self.camera_controller.is_connected:
            self.lbl_cam_status.setText("Camera: Connected")
            self.lbl_cam_status.setStyleSheet("color: #2ecc71; border: none; font-weight: bold;")
        else:
            self.lbl_cam_status.setText("Camera: Disconnected")
            self.lbl_cam_status.setStyleSheet("color: red; border: none; font-weight: bold;")

    def record_event(self, level, message):
        if level == "warning":
            self._last_warning_message = message
        if hasattr(self.diagnostics_widget, "add_entry"):
            self.diagnostics_widget.add_entry(level, message)
        self.status_bar.showMessage(message)
        print(f"[{_current_utc_timestamp()}][{level.upper()}] {message}")

    def connect_avp_from_dashboard(self):
        settings = self.dashboard_widget.get_avp_settings()
        ip = settings.get("ip") or getattr(config, "AVP_IP", "")
        auto_reconnect = bool(settings.get("auto_reconnect", False))
        save_avp_connection_settings(ip, auto_reconnect)
        if self.client is None:
            self.client = self._create_client(ip)
        if hasattr(self.client, "connect"):
            self.client.connect(ip=ip, auto_reconnect=auto_reconnect)
        self.propagate_dependencies()
        self.record_event("info", f"正在连接 AVP Client: {ip}")
        self.refresh_system_snapshot()

    def disconnect_avp_from_dashboard(self):
        if self.client and hasattr(self.client, "disconnect"):
            self.client.disconnect()
        self.record_event("info", "已断开 AVP Client。")
        self.refresh_system_snapshot()

    def retry_avp_from_dashboard(self):
        if self.client is None:
            return self.connect_avp_from_dashboard()
        if hasattr(self.client, "retry_now"):
            self.client.retry_now()
        self.record_event("info", "已手动触发 AVP 重连。")
        self.refresh_system_snapshot()

    def check_avp_from_dashboard(self):
        if self.client is None:
            self.record_event("warning", "AVP 尚未连接，请先点击 Connect AVP。")
            return

        pose_status = self._avp_pose_status()
        connection_status = self._avp_connection_status()
        reason = pose_status.get("reason", "")

        if reason == "streamer_initializing":
            age = pose_status.get("state_age_sec", connection_status.get("state_age_sec", 0.0))
            self.record_event(
                "warning",
                f"AVP Tracking Streamer 正在初始化，请确认 Vision Pro 端已点击 Start。当前已等待 {age:.1f}s。",
            )
            return
        if reason == "streamer_import_failed":
            self.record_event("warning", f"AVP 依赖导入失败：{pose_status.get('error', 'unknown error')}")
            return
        if reason == "stream_established_waiting_first_sample":
            self.record_event("warning", "AVP 已连接，但仍在等待首帧头姿。请确认 Vision Pro App 已打开并点击 Start。")
            return
        if pose_status.get("valid"):
            self.record_event("info", "AVP 姿态输入正常。")
            return

        state = connection_status.get("state", "idle")
        if state == "idle":
            self.record_event("warning", "AVP 尚未连接，请先点击 Connect AVP。")
        else:
            self.record_event("warning", f"AVP 当前状态异常：{reason or state}")

    def connect_motor_from_dashboard(self):
        self.record_event("info", "正在从主控台尝试连接电机。")
        self.dxl_debug.btn_connect.click()

    def connect_camera_from_dashboard(self):
        self.on_camera_connection_requested(True)
        if self.camera_controller.is_connected:
            self.record_event("info", "ZED 相机已连接。")

    def start_stream_from_dashboard(self):
        self.start_stream()
        if self.teleop_widget.is_streaming:
            self.record_event("info", "已从主控台开启传输。")

    def motor_init_from_dashboard(self):
        if hasattr(self.pose_widget, "move_to_tracking_start_pose") and self.pose_widget.move_to_tracking_start_pose():
            self.record_event("info", "电机初始化完成：已移动到追踪初始位。")
            self.refresh_system_snapshot()

    def pose_init_from_dashboard(self):
        if hasattr(self.pose_widget, "initialize_pose_sync") and self.pose_widget.initialize_pose_sync():
            self.record_event("info", "头姿初始化完成。")
            self.refresh_system_snapshot()

    def start_tracking_from_dashboard(self):
        if not getattr(self.pose_widget, "motor_initialized", False) or not getattr(self.pose_widget, "pose_initialized", False):
            self.record_event("warning", "跟踪前请先完成电机初始化与头姿初始化。")
            return
        if not self.teleop_widget.is_streaming:
            self.record_event("warning", "传输未开启，请先连接 ZED 相机并开启传输。")
            return
        if hasattr(self.pose_widget, "start_tracking_sequence") and self.pose_widget.start_tracking_sequence():
            self.record_event("info", "已从主控台发起开始跟踪。")
            self.refresh_system_snapshot()

    def stop_tracking_from_dashboard(self):
        self.pose_widget.toggle_tracking(False)
        self.record_event("warning", "已停止跟踪。")
        self.refresh_system_snapshot()

    def safe_reset(self):
        if getattr(self.pose_widget, "is_tracking", False):
            self.pose_widget.toggle_tracking(False)
        result = True
        if hasattr(self.pose_widget, "move_to_tracking_start_pose"):
            result = self.pose_widget.move_to_tracking_start_pose()
        if result:
            self.record_event("warning", "已执行安全复位。")
        else:
            self.record_event("warning", "安全复位失败：无法回到追踪初始位。")
        self.refresh_system_snapshot()

    def on_cam_param_changed(self, name, value):
        if name == "EXPOSURE":
            self.camera_controller.set_exposure(value)
        elif name == "WHITEBALANCE":
            self.camera_controller.set_whitebalance(value)
        elif name == "GAIN":
            self.camera_controller.set_gain(value)

    def on_cam_auto_exp(self, enabled):
        self.camera_controller.set_auto_exposure(enabled)

    def on_cam_auto_wb(self, enabled):
        self.camera_controller.set_auto_whitebalance(enabled)

    def on_cam_confidence(self, value):
        self.camera_controller.set_confidence_threshold(value)

    def on_cam_disparity(self, value):
        self.camera_controller.set_disparity_range(value)

    def on_cam_mode(self, mode):
        self.camera_controller.set_view_mode(mode)

    def on_cam_focus(self, value):
        self.camera_controller.set_focus(value)

    def on_cam_auto_focus(self, enabled):
        self.camera_controller.set_auto_focus(enabled)

    def on_rtp_stream_requested(self, enabled, codec, bitrate, port):
        decision = precheck_rtp_stream_request(
            has_camera=self.camera_controller.is_connected,
            requested_enabled=enabled,
        )
        if not decision["accepted"]:
            if hasattr(self.camera_widget, "set_rtp_stream_ui_state"):
                self.camera_widget.set_rtp_stream_ui_state(decision["ui_state"]["checked"])
            if decision["warning"]:
                QMessageBox.warning(self, "Error", decision["warning"])
            return

        try:
            if enabled:
                if not self.camera_controller.enable_streaming(codec=codec, bitrate=bitrate, port=port):
                    raise RuntimeError("Failed to start ZED SDK RTP streaming.")
                self.status_bar.showMessage(f"RTP Streaming Started ({codec} @ {port})")
            else:
                self.camera_controller.disable_streaming()
                self.status_bar.showMessage("RTP Streaming Stopped")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"RTP Streaming Error: {exc}")
            if hasattr(self.camera_widget, "set_rtp_stream_ui_state"):
                self.camera_widget.set_rtp_stream_ui_state(False)
        finally:
            self.refresh_camera_diagnostics(force=True)
            self.refresh_system_snapshot()

    def on_camera_connection_requested(self, should_connect):
        try:
            if should_connect:
                res, fps, _, _, _ = self.teleop_widget.get_config()
                camera = self.camera_controller.open_camera(resolution=res, fps=fps)
                if camera is None:
                    raise RuntimeError("Failed to open camera.")
                self.status_bar.showMessage("Camera connected.")
            else:
                if self.teleop_widget.is_streaming:
                    self.stop_stream()
                self.camera_controller.close_camera()
                self.status_bar.showMessage("Camera disconnected.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Camera connection error: {exc}")
        finally:
            self.refresh_camera_diagnostics(force=True)
            self.refresh_system_snapshot()

    def _avp_ready_for_stream(self):
        if not self.client:
            return False, "AVP client is not ready yet."
        state = self._avp_connection_status().get("state", "idle")
        if state != "ready":
            return False, f"AVP client is {state}."
        return True, ""

    def start_stream(self):
        ready, reason = self._avp_ready_for_stream()
        if not ready:
            QMessageBox.warning(self, "Error", reason)
            self.teleop_widget.set_streaming_state(False)
            return False

        res, fps, bitrate, stereo, latency = self.teleop_widget.get_config()
        if not self.camera_controller.is_connected:
            camera = self.camera_controller.open_camera(resolution=res, fps=fps)
            if camera is None:
                QMessageBox.critical(self, "Error", "Failed to open camera.")
                self.teleop_widget.set_streaming_state(False)
                return False

        try:
            self.client.start_video_stream(
                frame_source=self.camera_controller,
                resolution=res,
                fps=fps,
                bitrate=bitrate,
                stereo=stereo,
                latency=latency,
            )
            self.teleop_widget.set_streaming_state(True)
            if hasattr(self.pose_widget, "set_streaming_ready"):
                self.pose_widget.set_streaming_ready(True)
            if hasattr(self.camera_widget, "update_info"):
                self.camera_widget.update_info(res, fps)
            self.refresh_camera_diagnostics(force=True)
            self.refresh_system_snapshot()
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to start stream: {exc}")
            self.teleop_widget.set_streaming_state(False)
            return False

    def stop_stream(self):
        if self.client:
            self.client.stop_video_stream()
        self.teleop_widget.set_streaming_state(False)
        if hasattr(self.pose_widget, "set_streaming_ready"):
            self.pose_widget.set_streaming_ready(False)
        self.refresh_camera_diagnostics(force=True)
        self.refresh_system_snapshot()

    def restart_stream(self, res, fps, bitrate, stereo, latency):
        if not self.client:
            return
        if not self.camera_controller.is_connected:
            camera = self.camera_controller.open_camera(resolution=res, fps=fps)
            if camera is None:
                QMessageBox.critical(self, "Error", "Failed to open camera for stream restart.")
                self.teleop_widget.set_streaming_state(False)
                return
        self.client.restart_video_stream(
            frame_source=self.camera_controller,
            resolution=res,
            fps=fps,
            bitrate=bitrate,
            stereo=stereo,
            latency=latency,
        )
        self.teleop_widget.set_streaming_state(True)
        self.refresh_camera_diagnostics(force=True)
        self.refresh_system_snapshot()

    def reconnect_camera(self):
        self.status_bar.showMessage("Reconnecting camera...")
        res, fps, _, _, _ = self.teleop_widget.get_config()
        self.camera_controller.close_camera()
        self.camera_controller.open_camera(resolution=res, fps=fps)
        self.refresh_camera_diagnostics(force=True)
        self.refresh_system_snapshot()

    def update_loop(self):
        current_index = self.tabs.currentIndex()
        if self.camera_controller.is_connected and current_index == 1:
            ret, frame = self.camera_controller.read()
            if ret and frame is not None:
                if self.teleop_widget.chk_mirror.isChecked():
                    frame = cv2.flip(frame, 1)
                if self.teleop_widget.chk_rotate.isChecked():
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                self.teleop_widget.update_frame(frame)
        self.refresh_camera_diagnostics()
        self.refresh_system_snapshot()

    def save_config(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Config", "", "JSON Files (*.json)")
        if path:
            data = {
                "mock_avp": config.MOCK_AVP,
                "mock_motors": config.MOCK_MOTORS,
            }
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=4)
            self.status_bar.showMessage(f"Config saved to {path}")

    def load_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Config", "", "JSON Files (*.json)")
        if path:
            self.status_bar.showMessage(f"Config loaded from {path} (Not applied logic yet)")

    def on_tab_changed(self, index):
        if index == 2:
            self.dxl_debug.start_monitoring()
        else:
            self.dxl_debug.stop_monitoring()

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self,
            "Confirm Exit",
            "Stop all streams and disconnect motors?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if getattr(self.pose_widget, "is_tracking", False):
                self.pose_widget.toggle_tracking(False)
            if self.teleop_widget.is_streaming:
                self.stop_stream()
            self.camera_controller.close_camera()
            if self.client:
                self.client.close()
            self.dxl_debug.clean_shutdown()
            event.accept()
        else:
            event.ignore()
