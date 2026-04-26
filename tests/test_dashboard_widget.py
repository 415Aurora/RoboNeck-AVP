import importlib
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

    def setLayout(self, layout):
        self._layout = layout


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


class QGridLayout(Layout):
    pass


class QLabel(QWidget):
    def __init__(self, text=""):
        super().__init__()
        self._text = text

    def setText(self, text):
        self._text = text

    def text(self):
        return self._text

    def setObjectName(self, _name):
        return None

    def setWordWrap(self, _value):
        return None


class QGroupBox(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self._title = title

    def title(self):
        return self._title


class QPushButton(QWidget):
    def __init__(self, text=""):
        super().__init__()
        self._text = text
        self.clicked = Signal()
        self._enabled = True
        self.minimum_height = None

    def text(self):
        return self._text

    def setMinimumHeight(self, value):
        self.minimum_height = value

    def setEnabled(self, value):
        self._enabled = bool(value)

    def isEnabled(self):
        return self._enabled

    def click(self):
        self.clicked.emit()


class QLineEdit(QWidget):
    def __init__(self, text=""):
        super().__init__()
        self._text = text

    def setText(self, text):
        self._text = text

    def text(self):
        return self._text


class QCheckBox(QWidget):
    def __init__(self, text=""):
        super().__init__()
        self._text = text
        self._checked = False

    def setChecked(self, value):
        self._checked = bool(value)

    def isChecked(self):
        return self._checked


def pyqtSignal(*args, **kwargs):
    return Signal()


def load_dashboard(monkeypatch):
    pyqt6 = types.ModuleType("PyQt6")
    qtwidgets = types.ModuleType("PyQt6.QtWidgets")
    qtcore = types.ModuleType("PyQt6.QtCore")

    qtwidgets.QWidget = QWidget
    qtwidgets.QVBoxLayout = QVBoxLayout
    qtwidgets.QHBoxLayout = QHBoxLayout
    qtwidgets.QGridLayout = QGridLayout
    qtwidgets.QGroupBox = QGroupBox
    qtwidgets.QLabel = QLabel
    qtwidgets.QPushButton = QPushButton
    qtwidgets.QLineEdit = QLineEdit
    qtwidgets.QCheckBox = QCheckBox
    qtcore.pyqtSignal = pyqtSignal

    monkeypatch.setitem(sys.modules, "PyQt6", pyqt6)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", qtcore)

    sys.modules.pop("src.gui.dashboard", None)
    return importlib.import_module("src.gui.dashboard")


def test_dashboard_uses_three_staged_flow_groups_and_named_buttons(monkeypatch):
    dashboard = load_dashboard(monkeypatch)

    widget = dashboard.DashboardWidget()

    assert widget.grp_device_flow.title() == "设备连接"
    assert widget.grp_init_flow.title() == "初始化"
    assert widget.grp_tracking_flow.title() == "跟踪控制"
    assert widget.btn_connect_motor.text() == "连接电机"
    assert widget.btn_check_avp.text() == "检查 AVP"
    assert widget.btn_connect_camera.text() == "连接 ZED 相机"
    assert widget.btn_start_stream.text() == "开启传输"
    assert widget.btn_motor_init.text() == "电机初始化"
    assert widget.btn_pose_init.text() == "头姿初始化"
    assert widget.btn_start.text() == "开始跟踪"
    assert widget.btn_stop.text() == "停止跟踪"
    assert widget.btn_safe_reset.text() == "安全复位"
    assert widget.input_avp_ip.text() != ""
    assert widget.btn_connect_avp.text() == "Connect AVP"
    assert widget.btn_disconnect_avp.text() == "Disconnect AVP"
    assert widget.btn_retry_avp.text() == "Retry AVP"


def test_dashboard_emits_split_action_signals(monkeypatch):
    dashboard = load_dashboard(monkeypatch)

    widget = dashboard.DashboardWidget()
    emitted = []
    widget.connect_motor_requested.connect(lambda: emitted.append("motor"))
    widget.check_avp_requested.connect(lambda: emitted.append("avp"))
    widget.connect_avp_requested.connect(lambda: emitted.append("connect_avp"))
    widget.disconnect_avp_requested.connect(lambda: emitted.append("disconnect_avp"))
    widget.retry_avp_requested.connect(lambda: emitted.append("retry_avp"))
    widget.connect_camera_requested.connect(lambda: emitted.append("camera"))
    widget.start_stream_requested.connect(lambda: emitted.append("stream"))
    widget.motor_init_requested.connect(lambda: emitted.append("motor_init"))
    widget.pose_init_requested.connect(lambda: emitted.append("pose_init"))

    widget.btn_connect_motor.click()
    widget.btn_check_avp.click()
    widget.btn_connect_avp.click()
    widget.btn_disconnect_avp.click()
    widget.btn_retry_avp.click()
    widget.btn_connect_camera.click()
    widget.btn_start_stream.click()
    widget.btn_motor_init.click()
    widget.btn_pose_init.click()

    assert emitted == [
        "motor",
        "avp",
        "connect_avp",
        "disconnect_avp",
        "retry_avp",
        "camera",
        "stream",
        "motor_init",
        "pose_init",
    ]


def test_dashboard_round_trips_manual_avp_settings(monkeypatch):
    dashboard = load_dashboard(monkeypatch)

    widget = dashboard.DashboardWidget()
    widget.set_avp_settings(ip="192.168.0.12", auto_reconnect=True)

    assert widget.get_avp_settings() == {
        "ip": "192.168.0.12",
        "auto_reconnect": True,
    }
