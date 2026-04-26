import importlib
import builtins
import os
import sys
import types


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)


class Signal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs):
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class QWidget:
    def __init__(self, parent=None):
        self.parent = parent
        self._layout = None
        self._enabled = True
        self._style = ""

    def setLayout(self, layout):
        self._layout = layout

    def setEnabled(self, value):
        self._enabled = value

    def isEnabled(self):
        return self._enabled

    def setStyleSheet(self, style):
        self._style = style


class QMainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.central_widget = None
        self.status_bar = None
        self.window_title = ""

    def setCentralWidget(self, widget):
        self.central_widget = widget

    def setStatusBar(self, status_bar):
        self.status_bar = status_bar

    def setWindowTitle(self, title):
        self.window_title = title

    def resize(self, width, height):
        self.size = (width, height)

    def close(self):
        self.closed = True


class Layout:
    def __init__(self, *args, **kwargs):
        self.items = []

    def addWidget(self, widget, *args):
        self.items.append(("widget", widget, args))

    def addLayout(self, layout, *args):
        self.items.append(("layout", layout, args))

    def addStretch(self):
        self.items.append(("stretch",))


class QVBoxLayout(Layout):
    pass


class QHBoxLayout(Layout):
    pass


class QTabWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._tabs = []
        self._index = 0
        self.currentChanged = Signal()

    def addTab(self, widget, label):
        self._tabs.append((widget, label))

    def count(self):
        return len(self._tabs)

    def tabText(self, index):
        return self._tabs[index][1]

    def currentIndex(self):
        return self._index

    def setCurrentIndex(self, index):
        self._index = index
        self.currentChanged.emit(index)


class QPushButton(QWidget):
    def __init__(self, text=""):
        super().__init__()
        self._text = text
        self.clicked = Signal()
        self._flat = False
        self._object_name = ""

    def setText(self, text):
        self._text = text

    def text(self):
        return self._text

    def click(self):
        self.clicked.emit()

    def setFlat(self, flat):
        self._flat = flat

    def setObjectName(self, name):
        self._object_name = name


class QStatusBar(QWidget):
    def __init__(self):
        super().__init__()
        self.message = ""
        self.widgets = []

    def showMessage(self, message):
        self.message = message

    def addPermanentWidget(self, widget):
        self.widgets.append(widget)


class QMessageBox:
    class StandardButton:
        Yes = 1
        No = 2

    @classmethod
    def question(cls, *args, **kwargs):
        return cls.StandardButton.Yes

    @classmethod
    def critical(cls, *args, **kwargs):
        return None

    @classmethod
    def warning(cls, *args, **kwargs):
        return None


class QFileDialog:
    @staticmethod
    def getSaveFileName(*args, **kwargs):
        return "", ""

    @staticmethod
    def getOpenFileName(*args, **kwargs):
        return "", ""


class QTimer:
    def __init__(self):
        self.timeout = Signal()
        self.started = False
        self.stopped = False

    def start(self, *args):
        self.started = True

    def stop(self):
        self.stopped = True


class QThread:
    def start(self):
        return None


def pyqtSignal(*args, **kwargs):
    return Signal()


class QIcon:
    pass


class FakeCheckbox:
    def isChecked(self):
        return False


class FakePoseControlWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.is_tracking = False
        self.is_tracking_paused = False
        self.runtime_event = Signal()
        self.retargeter = types.SimpleNamespace(calibrated=False)
        self.dependencies = None
        self.start_sequence_calls = 0
        self.streaming_ready = False
        self.move_to_tracking_start_pose_calls = 0
        self.move_to_tracking_start_pose_result = True
        self.initialize_pose_sync_calls = 0
        self.initialize_pose_sync_result = True
        self.motor_initialized = False
        self.pose_initialized = False
        self.btn_track = types.SimpleNamespace(toggled=Signal())

    def set_dependencies(self, motors, client, camera_controller=None):
        self.dependencies = (motors, client, camera_controller)

    def set_streaming_ready(self, ready):
        self.streaming_ready = ready

    def start_tracking_sequence(self):
        self.start_sequence_calls += 1
        self.is_tracking = True
        return True

    def move_to_tracking_start_pose(self):
        self.move_to_tracking_start_pose_calls += 1
        if self.move_to_tracking_start_pose_result:
            self.motor_initialized = True
            self.pose_initialized = False
        return self.move_to_tracking_start_pose_result

    def initialize_pose_sync(self):
        self.initialize_pose_sync_calls += 1
        if self.initialize_pose_sync_result:
            self.pose_initialized = True
        return self.initialize_pose_sync_result

    def toggle_tracking(self, checked):
        self.is_tracking = checked

    def calibrate(self):
        self.retargeter.calibrated = True


class FakeCameraParamWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.connected = False
        self.param_changed = Signal()
        self.auto_exposure_toggled = Signal()
        self.auto_wb_toggled = Signal()
        self.confidence_changed = Signal()
        self.disparity_changed = Signal()
        self.capture_mode_changed = Signal()
        self.focus_changed = Signal()
        self.auto_focus_toggled = Signal()
        self.rtp_stream_requested = Signal()
        self.camera_connection_requested = Signal()
        self.btn_rtp_stream = QPushButton()

    def set_connected(self, connected):
        self.connected = connected

    def update_info(self, res, fps):
        self.info = (res, fps)


class FakeTeleopStreamWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.is_streaming = False
        self.start_stream_requested = Signal()
        self.stop_stream_requested = Signal()
        self.restart_stream_requested = Signal()
        self.chk_mirror = FakeCheckbox()
        self.chk_rotate = FakeCheckbox()

    def get_config(self):
        return "3840x1080", 30, 20000, True, "Balanced"

    def update_frame(self, frame):
        self.frame = frame

    def update_stats(self, *args):
        self.stats = args

    def set_streaming_state(self, state):
        self.is_streaming = state


class FakeDxlDebugWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.motor_connected = Signal()
        self.monitor_started = False
        self.reset_zero_called = False
        self._controller = types.SimpleNamespace(connected=True)
        self.btn_connect = QPushButton()

    def start_monitoring(self):
        self.monitor_started = True

    def stop_monitoring(self):
        self.monitor_started = False

    def clean_shutdown(self):
        self.cleaned = True

    def on_reset_zero(self):
        self.reset_zero_called = True


class FakeDashboardWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.snapshot = None
        self.connect_motor_requested = Signal()
        self.check_avp_requested = Signal()
        self.connect_avp_requested = Signal()
        self.disconnect_avp_requested = Signal()
        self.retry_avp_requested = Signal()
        self.connect_camera_requested = Signal()
        self.start_stream_requested = Signal()
        self.motor_init_requested = Signal()
        self.pose_init_requested = Signal()
        self.start_tracking_requested = Signal()
        self.stop_tracking_requested = Signal()
        self.safe_reset_requested = Signal()
        self.open_camera_tools_requested = Signal()
        self.open_motor_tools_requested = Signal()
        self.open_diagnostics_requested = Signal()
        self.avp_settings = {"ip": "172.20.10.2", "auto_reconnect": False}
        self.avp_runtime = None

    def update_system_snapshot(self, snapshot):
        self.snapshot = snapshot

    def get_avp_settings(self):
        return dict(self.avp_settings)

    def set_avp_settings(self, ip, auto_reconnect):
        self.avp_settings = {"ip": ip, "auto_reconnect": bool(auto_reconnect)}

    def update_avp_runtime(self, runtime):
        self.avp_runtime = dict(runtime)


class FakeCameraStreamPage(QWidget):
    def __init__(self, camera_widget, teleop_widget):
        super().__init__()
        self.camera_widget = camera_widget
        self.teleop_widget = teleop_widget


class FakeMotorCalibrationPage(QWidget):
    def __init__(self, pose_widget, dxl_debug):
        super().__init__()
        self.pose_widget = pose_widget
        self.dxl_debug = dxl_debug


class FakeDiagnosticsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.snapshot = None
        self.entries = []
        self.label_warning = types.SimpleNamespace(text=lambda: "")
        self._last_warning = ""

    def update_system_snapshot(self, snapshot):
        self.snapshot = snapshot
        self._last_warning = snapshot.last_warning
        self.label_warning = types.SimpleNamespace(text=lambda: self._last_warning)

    def add_entry(self, level, message):
        self.entries.append((level, message))


class FakeClient:
    def __init__(self, ip=None, pose_status=None):
        self.ip = ip or "172.20.10.2"
        self.camera = None
        self.connect_calls = []
        self.disconnect_calls = 0
        self.retry_calls = 0
        self.connection_status = {
            "state": "ready",
            "ip": self.ip,
            "auto_reconnect": False,
            "last_error": None,
            "state_age_sec": 0.0,
            "last_sample_timestamp": None,
            "has_ever_received_pose": True,
        }
        self.pose_status = pose_status or {
            "valid": True,
            "reason": "",
            "fresh": True,
        }
        self.preflight_error = None

    def connect(self, ip=None, auto_reconnect=True):
        self.connect_calls.append({"ip": ip or self.ip, "auto_reconnect": bool(auto_reconnect)})
        self.ip = ip or self.ip
        self.connection_status.update(
            {
                "state": "connecting",
                "ip": self.ip,
                "auto_reconnect": bool(auto_reconnect),
                "last_error": None,
            }
        )
        return True

    def disconnect(self):
        self.disconnect_calls += 1
        self.connection_status["state"] = "disconnected"

    def retry_now(self):
        self.retry_calls += 1
        self.connection_status["state"] = "reconnecting"
        return True

    def start_video_stream(self, *args, **kwargs):
        self.camera = types.SimpleNamespace(is_opened=True, read=lambda: (False, None))

    def stop_video_stream(self):
        self.camera = None

    def restart_video_stream(self, *args, **kwargs):
        self.camera = types.SimpleNamespace(is_opened=True, read=lambda: (False, None))

    def get_pose_status(self):
        return dict(self.pose_status)

    def get_connection_status(self):
        return dict(self.connection_status)


class FakeCameraController:
    def __init__(self):
        self.is_connected = False
        self.open_calls = []
        self.close_calls = 0
        self.streaming_enabled = False

    def open_camera(self, resolution=None, fps=None):
        self.open_calls.append((resolution, fps))
        self.is_connected = True
        return types.SimpleNamespace(is_opened=True)

    def close_camera(self):
        self.close_calls += 1
        self.is_connected = False

    def read(self):
        return False, None

    def get_device_info(self):
        return {}

    def get_sensor_snapshot(self):
        return {}

    def get_health_status(self):
        return {}

    def get_streaming_status(self):
        return {"enabled": self.streaming_enabled}

    def enable_streaming(self, codec="H264", bitrate=8000, port=30000):
        self.streaming_enabled = True
        return True

    def disable_streaming(self):
        self.streaming_enabled = False
        return True

    def set_exposure(self, value):
        return True

    def set_whitebalance(self, value):
        return True

    def set_gain(self, value):
        return True

    def set_auto_exposure(self, enabled):
        return True

    def set_auto_whitebalance(self, enabled):
        return True

    def set_confidence_threshold(self, value):
        return True

    def set_disparity_range(self, value):
        return True

    def set_view_mode(self, mode):
        return True

    def set_focus(self, value):
        return True

    def set_auto_focus(self, enabled):
        return True


def load_main_window(monkeypatch):
    pyqt6 = types.ModuleType("PyQt6")
    qtwidgets = types.ModuleType("PyQt6.QtWidgets")
    qtcore = types.ModuleType("PyQt6.QtCore")
    qtgui = types.ModuleType("PyQt6.QtGui")

    qtwidgets.QMainWindow = QMainWindow
    qtwidgets.QWidget = QWidget
    qtwidgets.QVBoxLayout = QVBoxLayout
    qtwidgets.QTabWidget = QTabWidget
    qtwidgets.QPushButton = QPushButton
    qtwidgets.QStatusBar = QStatusBar
    qtwidgets.QMessageBox = QMessageBox
    qtwidgets.QHBoxLayout = QHBoxLayout
    qtwidgets.QFileDialog = QFileDialog
    qtcore.Qt = object()
    qtcore.QTimer = QTimer
    qtcore.QThread = QThread
    qtcore.pyqtSignal = pyqtSignal
    qtgui.QIcon = QIcon

    monkeypatch.setitem(sys.modules, "PyQt6", pyqt6)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PyQt6.QtGui", qtgui)
    monkeypatch.setitem(sys.modules, "cv2", types.SimpleNamespace())

    monkeypatch.setitem(sys.modules, "src.gui.pose_control", types.SimpleNamespace(PoseControlWidget=FakePoseControlWidget))
    monkeypatch.setitem(sys.modules, "src.gui.camera_param", types.SimpleNamespace(CameraParamWidget=FakeCameraParamWidget))
    monkeypatch.setitem(sys.modules, "src.gui.teleop_stream", types.SimpleNamespace(TeleopStreamWidget=FakeTeleopStreamWidget))
    monkeypatch.setitem(sys.modules, "src.gui.dynamixel_debug", types.SimpleNamespace(DxlDebugWidget=FakeDxlDebugWidget))
    monkeypatch.setitem(sys.modules, "src.gui.dashboard", types.SimpleNamespace(DashboardWidget=FakeDashboardWidget))
    monkeypatch.setitem(sys.modules, "src.gui.camera_stream", types.SimpleNamespace(CameraStreamPage=FakeCameraStreamPage))
    monkeypatch.setitem(sys.modules, "src.gui.motor_calibration", types.SimpleNamespace(MotorCalibrationPage=FakeMotorCalibrationPage))
    monkeypatch.setitem(sys.modules, "src.gui.diagnostics", types.SimpleNamespace(DiagnosticsWidget=FakeDiagnosticsWidget))
    monkeypatch.setitem(sys.modules, "src.core.camera_controller", types.SimpleNamespace(CameraController=FakeCameraController))
    monkeypatch.setitem(sys.modules, "src.core.client", types.SimpleNamespace(AVPClient=FakeClient))
    monkeypatch.setitem(sys.modules, "src.core.mock_client", types.SimpleNamespace(MockAVPClient=FakeClient))
    monkeypatch.setitem(
        sys.modules,
        "src.core.avp_connection",
        types.SimpleNamespace(
            load_avp_connection_settings=lambda: {"ip": "172.20.10.2", "auto_reconnect": False},
            save_avp_connection_settings=lambda ip, auto_reconnect: {"ip": ip, "auto_reconnect": auto_reconnect},
        ),
    )

    sys.modules.pop("src.gui.main_window", None)
    return importlib.import_module("src.gui.main_window")


def test_main_window_uses_dashboard_first_and_groups_tool_pages(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()

    assert window.tabs.count() == 4
    assert window.tabs.tabText(0) == "主控台"
    assert window.tabs.tabText(1) == "相机与串流"
    assert window.tabs.tabText(2) == "电机与初始化"
    assert window.tabs.tabText(3) == "诊断与日志"


def test_main_window_starts_without_automatic_avp_initialization(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()

    assert window.client is None
    assert window.dashboard_widget.get_avp_settings() == {
        "ip": "172.20.10.2",
        "auto_reconnect": False,
    }
    assert window.dashboard_widget.snapshot.avp_connected is False


def test_connect_avp_from_dashboard_creates_client_and_uses_manual_settings(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.dashboard_widget.set_avp_settings(ip="192.168.0.12", auto_reconnect=True)

    window.connect_avp_from_dashboard()

    assert window.client is not None
    assert window.client.connect_calls == [
        {"ip": "192.168.0.12", "auto_reconnect": True}
    ]
    assert window.diagnostics_widget.entries[-1] == ("info", "正在连接 AVP Client: 192.168.0.12")


def test_disconnect_avp_from_dashboard_stops_client_without_recreating_it(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.on_client_ready(FakeClient())

    window.disconnect_avp_from_dashboard()

    assert window.client.disconnect_calls == 1
    assert window.diagnostics_widget.entries[-1] == ("info", "已断开 AVP Client。")


def test_main_window_reports_snapshot_to_dashboard(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.on_client_ready(FakeClient())
    window.on_motor_connection_changed(types.SimpleNamespace(connected=True))
    window.pose_widget.retargeter.calibrated = True
    window.pose_widget.is_tracking = True
    window.refresh_system_snapshot()

    snapshot = window.dashboard_widget.snapshot

    assert snapshot.avp_connected is True
    assert snapshot.motor_connected is True
    assert snapshot.pose_initialized is False
    assert snapshot.tracking is True
    assert snapshot.pose_sample_valid is True


def test_main_window_snapshot_marks_paused_tracking_session(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.on_client_ready(FakeClient(pose_status={"valid": False, "reason": "stale_sample", "fresh": False}))
    window.on_motor_connection_changed(types.SimpleNamespace(connected=True, motors_ready=True))
    window.pose_widget.is_tracking = True
    window.pose_widget.is_tracking_paused = True
    window.refresh_system_snapshot()

    snapshot = window.dashboard_widget.snapshot

    assert snapshot.tracking is True
    assert snapshot.tracking_paused is True
    assert snapshot.pose_sample_reason == "stale_sample"


def test_main_window_snapshot_marks_connected_but_unready_motors(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.on_client_ready(FakeClient())
    window.on_motor_connection_changed(
        types.SimpleNamespace(connected=True, motors_ready=False, motor_error="无法读取电机当前位置")
    )
    window.refresh_system_snapshot()

    snapshot = window.dashboard_widget.snapshot

    assert snapshot.motor_connected is True
    assert snapshot.motor_ready is False
    assert snapshot.motor_reason == "无法读取电机当前位置"


def test_main_window_snapshot_distinguishes_avp_client_from_invalid_pose_stream(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.on_client_ready(FakeClient(pose_status={"valid": False, "reason": "missing_head_field", "fresh": False}))
    window.refresh_system_snapshot()

    snapshot = window.dashboard_widget.snapshot

    assert snapshot.avp_connected is True
    assert snapshot.pose_sample_valid is False
    assert snapshot.pose_sample_reason == "missing_head_field"


def test_main_window_snapshot_surfaces_streamer_initializing_reason(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.on_client_ready(
        FakeClient(pose_status={"valid": False, "reason": "streamer_initializing", "fresh": False})
    )
    window.refresh_system_snapshot()

    snapshot = window.dashboard_widget.snapshot

    assert snapshot.avp_connected is True
    assert snapshot.pose_sample_valid is False
    assert snapshot.pose_sample_reason == "streamer_initializing"


def test_check_avp_from_dashboard_reports_actionable_streamer_initializing_message(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.on_client_ready(
        FakeClient(pose_status={"valid": False, "reason": "streamer_initializing", "fresh": False, "state_age_sec": 4.8})
    )

    window.check_avp_from_dashboard()

    assert "Tracking Streamer" in window.diagnostics_widget.entries[-1][1]
    assert "Start" in window.diagnostics_widget.entries[-1][1]
    assert "4.8s" in window.diagnostics_widget.entries[-1][1]


def test_check_avp_from_dashboard_reports_import_error_detail(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.on_client_ready(
        FakeClient(
            pose_status={
                "valid": False,
                "reason": "streamer_import_failed",
                "fresh": False,
                "error": "No module named 'grpc'",
            }
        )
    )

    window.check_avp_from_dashboard()

    assert "grpc" in window.diagnostics_widget.entries[-1][1]


def test_main_window_records_warning_into_diagnostics(monkeypatch):
    main_window = load_main_window(monkeypatch)
    printed = []
    monkeypatch.setattr(main_window, "_current_utc_timestamp", lambda: "2026-04-03 11:00:00 UTC", raising=False)
    monkeypatch.setattr(builtins, "print", lambda *args, **kwargs: printed.append((args, kwargs)))

    window = main_window.MainWindow()
    window.record_event("warning", "Camera feed lost.")
    window.refresh_system_snapshot()

    assert window.diagnostics_widget.entries[-1] == ("warning", "Camera feed lost.")
    assert "Camera feed lost." in window.diagnostics_widget.label_warning.text()
    assert printed[-1][0][0] == "[2026-04-03 11:00:00 UTC][WARNING] Camera feed lost."


def test_main_window_forwards_pose_runtime_events_to_diagnostics(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.pose_widget.runtime_event.emit("warning", "[TRACK] PAUSED reason=stale_sample")

    assert window.diagnostics_widget.entries[-1] == ("warning", "[TRACK] PAUSED reason=stale_sample")
    assert window.status_bar.message == "[TRACK] PAUSED reason=stale_sample"


def test_connect_motor_from_dashboard_records_attempt_before_connection_result(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.on_client_ready(FakeClient())
    window.dxl_debug.btn_connect.clicked.connect(
        lambda: window.dxl_debug.motor_connected.emit(
            types.SimpleNamespace(
                connected=True,
                motors_ready=False,
                motor_error="无法 ping 通电机 ID 1：COMM_RX_TIMEOUT",
            )
        )
    )

    window.connect_motor_from_dashboard()

    assert window.diagnostics_widget.entries[-2:] == [
        ("info", "正在从主控台尝试连接电机。"),
        ("warning", "串口已连接，但电机未就绪：无法 ping 通电机 ID 1：COMM_RX_TIMEOUT"),
    ]


def test_connect_camera_from_dashboard_requests_camera_connection_without_starting_stream(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.on_client_ready(FakeClient())

    window.connect_camera_from_dashboard()

    assert window.camera_controller.open_calls == [("3840x1080", 30)]
    assert window.teleop_widget.is_streaming is False
    assert window.diagnostics_widget.entries[-1] == ("info", "ZED 相机已连接。")


def test_start_stream_from_dashboard_starts_stream_without_tracking(monkeypatch):
    main_window = load_main_window(monkeypatch)

    client = FakeClient()
    window = main_window.MainWindow()
    window.on_client_ready(client)

    window.start_stream_from_dashboard()

    assert window.teleop_widget.is_streaming is True
    assert window.pose_widget.start_sequence_calls == 0
    assert window.pose_widget.is_tracking is False
    assert window.diagnostics_widget.entries[-1] == ("info", "已从主控台开启传输。")


def test_motor_init_from_dashboard_moves_to_tracking_start_pose(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.on_client_ready(FakeClient())
    window.on_motor_connection_changed(types.SimpleNamespace(connected=True, motors_ready=True))

    window.motor_init_from_dashboard()

    assert window.pose_widget.move_to_tracking_start_pose_calls == 1
    assert window.pose_widget.motor_initialized is True
    assert window.pose_widget.pose_initialized is False
    assert window.diagnostics_widget.entries[-1] == ("info", "电机初始化完成：已移动到追踪初始位。")


def test_pose_init_from_dashboard_syncs_without_entering_tracking(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.on_client_ready(FakeClient())
    window.on_motor_connection_changed(types.SimpleNamespace(connected=True, motors_ready=True))
    window.pose_widget.motor_initialized = True
    window.teleop_widget.set_streaming_state(True)

    window.pose_init_from_dashboard()

    assert window.pose_widget.initialize_pose_sync_calls == 1
    assert window.pose_widget.pose_initialized is True
    assert window.pose_widget.is_tracking is False
    assert window.diagnostics_widget.entries[-1] == ("info", "头姿初始化完成。")


def test_start_tracking_from_dashboard_requires_explicit_initialization(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.on_client_ready(FakeClient())
    window.on_motor_connection_changed(types.SimpleNamespace(connected=True, motors_ready=True))
    window.teleop_widget.set_streaming_state(True)

    window.start_tracking_from_dashboard()

    assert window.pose_widget.start_sequence_calls == 0
    assert window.pose_widget.is_tracking is False
    assert window.diagnostics_widget.entries[-1] == ("warning", "跟踪前请先完成电机初始化与头姿初始化。")


def test_start_tracking_from_dashboard_does_not_start_stream_implicitly(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.on_client_ready(FakeClient())
    window.on_motor_connection_changed(types.SimpleNamespace(connected=True, motors_ready=True))
    window.pose_widget.motor_initialized = True
    window.pose_widget.pose_initialized = True

    window.start_tracking_from_dashboard()

    assert window.teleop_widget.is_streaming is False
    assert window.pose_widget.start_sequence_calls == 0
    assert window.pose_widget.is_tracking is False
    assert window.diagnostics_widget.entries[-1] == ("warning", "传输未开启，请先连接 ZED 相机并开启传输。")


def test_start_tracking_from_dashboard_starts_tracking_after_explicit_flow(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.on_client_ready(FakeClient())
    window.on_motor_connection_changed(types.SimpleNamespace(connected=True, motors_ready=True))
    window.teleop_widget.set_streaming_state(True)
    window.pose_widget.motor_initialized = True
    window.pose_widget.pose_initialized = True

    window.start_tracking_from_dashboard()

    assert window.pose_widget.start_sequence_calls == 1
    assert window.pose_widget.is_tracking is True
    assert window.diagnostics_widget.entries[-1] == ("info", "已从主控台发起开始跟踪。")


def test_safe_reset_stops_tracking_and_moves_to_tracking_start_pose(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.on_client_ready(FakeClient())
    window.on_motor_connection_changed(types.SimpleNamespace(connected=True))
    window.pose_widget.is_tracking = True

    window.safe_reset()

    assert window.pose_widget.is_tracking is False
    assert window.pose_widget.move_to_tracking_start_pose_calls == 1
    assert window.dxl_debug.reset_zero_called is False
    assert window.diagnostics_widget.entries[-1] == ("warning", "已执行安全复位。")


def test_safe_reset_records_warning_when_tracking_start_pose_reset_fails(monkeypatch):
    main_window = load_main_window(monkeypatch)

    window = main_window.MainWindow()
    window.on_client_ready(FakeClient())
    window.on_motor_connection_changed(types.SimpleNamespace(connected=True))
    window.pose_widget.move_to_tracking_start_pose_result = False

    window.safe_reset()

    assert window.pose_widget.move_to_tracking_start_pose_calls == 1
    assert window.dxl_debug.reset_zero_called is False
    assert window.diagnostics_widget.entries[-1][0] == "warning"
    assert "追踪初始位" in window.diagnostics_widget.entries[-1][1]
