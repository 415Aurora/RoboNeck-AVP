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


class QGroupBox(QWidget):
    pass


class Layout:
    def __init__(self, *args, **kwargs):
        self.items = []

    def addWidget(self, widget, *args):
        self.items.append(("widget", widget, args))

    def addLayout(self, layout, *args):
        self.items.append(("layout", layout, args))


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

    def setStyleSheet(self, style):
        self._style = style


class QComboBox(QWidget):
    def __init__(self):
        super().__init__()
        self._items = []
        self._index = -1

    def addItem(self, text, user_data=None):
        self._items.append((text, user_data))
        if self._index == -1:
            self._index = 0

    def addItems(self, texts):
        for text in texts:
            self.addItem(text, text)

    def currentText(self):
        if self._index < 0:
            return ""
        return self._items[self._index][0]

    def setEditable(self, value):
        self._editable = value


class QPushButton(QWidget):
    def __init__(self, text=""):
        super().__init__()
        self._text = text
        self._checked = False
        self._checkable = False
        self._signals_blocked = False
        self.clicked = Signal()

    def setCheckable(self, value):
        self._checkable = value

    def setText(self, text):
        self._text = text

    def text(self):
        return self._text

    def setStyleSheet(self, style):
        self._style = style

    def setChecked(self, value):
        self._checked = bool(value)

    def isChecked(self):
        return self._checked

    def click(self):
        self.clicked.emit()

    def blockSignals(self, blocked):
        previous = self._signals_blocked
        self._signals_blocked = blocked
        return previous


class QLineEdit(QWidget):
    def __init__(self, text=""):
        super().__init__()
        self._text = str(text)

    def setReadOnly(self, value):
        self._read_only = value

    def setText(self, text):
        self._text = str(text)

    def text(self):
        return self._text

    def setStyleSheet(self, style):
        self._style = style


class QSlider(QWidget):
    def __init__(self, *_args):
        super().__init__()
        self._value = 0
        self.sliderReleased = Signal()
        self.valueChanged = Signal()

    def setRange(self, minimum, maximum):
        self._range = (minimum, maximum)

    def setValue(self, value):
        self._value = int(value)
        self.valueChanged.emit(self._value)

    def value(self):
        return self._value


class QTextBrowser(QWidget):
    def __init__(self):
        super().__init__()
        self.lines = []

    def setMaximumHeight(self, height):
        self._max_height = height

    def append(self, text):
        self.lines.append(text)


class QCheckBox(QWidget):
    def __init__(self, text=""):
        super().__init__()
        self._text = text
        self._checked = False
        self._signals_blocked = False
        self.toggled = Signal()

    def setChecked(self, value):
        changed = self._checked != bool(value)
        self._checked = bool(value)
        if changed and not self._signals_blocked:
            self.toggled.emit(self._checked)

    def isChecked(self):
        return self._checked

    def blockSignals(self, blocked):
        previous = self._signals_blocked
        self._signals_blocked = blocked
        return previous


class QSpinBox(QWidget):
    def __init__(self):
        super().__init__()
        self._value = 0

    def setRange(self, minimum, maximum):
        self._range = (minimum, maximum)

    def setValue(self, value):
        self._value = int(value)

    def value(self):
        return self._value


class QMessageBox:
    infos = []
    warnings = []

    @classmethod
    def information(cls, parent, title, text):
        cls.infos.append((title, text))

    @classmethod
    def warning(cls, parent, title, text):
        cls.warnings.append((title, text))

    @classmethod
    def reset(cls):
        cls.infos = []
        cls.warnings = []


class QTimer:
    def __init__(self):
        self.timeout = Signal()
        self.interval_ms = None
        self.running = False

    def setInterval(self, interval_ms):
        self.interval_ms = interval_ms

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def isActive(self):
        return self.running


class QColor:
    def __init__(self, *_args, **_kwargs):
        pass


def pyqtSignal(*_args, **_kwargs):
    return Signal()


class FakeMotorController:
    def __init__(self, yaw_steps=2048, pitch_steps=2048, connected=True):
        self.connected = connected
        self.positions = {1: yaw_steps, 2: pitch_steps}
        self.goal_positions = []
        self.torque_calls = []

    def get_present_position(self, motor_id):
        return self.positions[motor_id]

    def set_goal_positions(self, commands):
        self.goal_positions.append(dict(commands))
        self.positions.update(commands)

    def enable_torque(self, motor_id, enabled):
        self.torque_calls.append((motor_id, enabled))

    def set_profile(self, *_args, **_kwargs):
        return None

    def set_pid(self, *_args, **_kwargs):
        return None

    def set_goal_pwm(self, *_args, **_kwargs):
        return None

    def read_detailed_status(self, motor_id):
        return {
            "position": self.positions[motor_id],
            "velocity": 0.0,
            "current": 0.0,
            "voltage": 12.0,
            "temperature": 25,
        }


class CapturingValidateMotorController(FakeMotorController):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validate_calls = []
        self.motors_ready = False
        self.motor_error = "无法 ping 通电机 ID 1：COMM_RX_TIMEOUT"

    def validate_motors(self, motor_ids, retries=3, initial_delay_sec=None, retry_delay_sec=None):
        self.validate_calls.append(
            {
                "motor_ids": tuple(motor_ids),
                "retries": retries,
                "initial_delay_sec": initial_delay_sec,
                "retry_delay_sec": retry_delay_sec,
            }
        )
        return False


class SequencedStatusMotorController(FakeMotorController):
    def __init__(self, statuses=None, ready=False, error="无法读取电机 ID 1 的状态。", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.statuses = {motor_id: list(values) for motor_id, values in (statuses or {}).items()}
        self.motors_ready = bool(ready)
        self.motor_error = "" if ready else str(error)
        self.readiness_calls = []

    def read_detailed_status(self, motor_id):
        queue = self.statuses.get(motor_id, [])
        if queue:
            return queue.pop(0)
        return None

    def set_motor_readiness(self, ready, error=""):
        self.readiness_calls.append((bool(ready), str(error)))
        self.motors_ready = bool(ready)
        self.motor_error = "" if ready else str(error)


class ProbeReportingMotorController(SequencedStatusMotorController):
    def __init__(self, probes=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.probes = dict(probes or {})

    def probe_motor(self, motor_id):
        return dict(
            self.probes.get(
                motor_id,
                {
                    "motor_id": int(motor_id),
                    "ping_ok": False,
                    "model_number": None,
                    "present_position": None,
                    "failed_stage": "ping",
                    "sdk_error": "COMM_RX_TIMEOUT",
                    "status_reads": {},
                },
            )
        )


def build_status(position):
    return {
        "position": int(position),
        "velocity": 0.0,
        "current": 0.0,
        "voltage": 12.0,
        "temperature": 25,
    }


class FakeMotorLimitStore:
    def __init__(self, limits=None):
        self.loaded = dict(
            limits
            or {
                "yaw_min_step": 0,
                "yaw_max_step": 4095,
                "pitch_min_step": 0,
                "pitch_max_step": 4095,
            }
        )
        self.saved = []

    def load(self):
        return dict(self.loaded)

    def save(self, yaw_min_step, yaw_max_step, pitch_min_step, pitch_max_step):
        payload = {
            "yaw_min_step": int(yaw_min_step),
            "yaw_max_step": int(yaw_max_step),
            "pitch_min_step": int(pitch_min_step),
            "pitch_max_step": int(pitch_max_step),
        }
        self.loaded = dict(payload)
        self.saved.append(dict(payload))
        return payload


class FakeTrackingStartStore:
    def __init__(self, yaw=2048, pitch=2048):
        self.loaded = {"yaw_start_step": int(yaw), "pitch_start_step": int(pitch)}

    def load(self):
        return dict(self.loaded)


def load_dynamixel_debug(monkeypatch):
    pyqt6 = types.ModuleType("PyQt6")
    qtwidgets = types.ModuleType("PyQt6.QtWidgets")
    qtcore = types.ModuleType("PyQt6.QtCore")
    qtgui = types.ModuleType("PyQt6.QtGui")

    qtwidgets.QWidget = QWidget
    qtwidgets.QGroupBox = QGroupBox
    qtwidgets.QVBoxLayout = QVBoxLayout
    qtwidgets.QHBoxLayout = QHBoxLayout
    qtwidgets.QGridLayout = QGridLayout
    qtwidgets.QLabel = QLabel
    qtwidgets.QComboBox = QComboBox
    qtwidgets.QPushButton = QPushButton
    qtwidgets.QLineEdit = QLineEdit
    qtwidgets.QSlider = QSlider
    qtwidgets.QMessageBox = QMessageBox
    qtwidgets.QTextBrowser = QTextBrowser
    qtwidgets.QCheckBox = QCheckBox
    qtwidgets.QSpinBox = QSpinBox
    qtcore.Qt = types.SimpleNamespace(Orientation=types.SimpleNamespace(Horizontal=1))
    qtcore.QTimer = QTimer
    qtcore.pyqtSignal = pyqtSignal
    qtgui.QColor = QColor

    monkeypatch.setitem(sys.modules, "PyQt6", pyqt6)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PyQt6.QtGui", qtgui)
    monkeypatch.setitem(sys.modules, "src.hardware.motor", types.SimpleNamespace(MotorController=FakeMotorController))
    monkeypatch.setitem(sys.modules, "src.hardware.mock_motor", types.SimpleNamespace(MockMotorController=FakeMotorController))
    sys.modules.pop("src.gui.dynamixel_debug", None)
    return importlib.import_module("src.gui.dynamixel_debug")


def test_prepare_limit_adjustment_disables_torque(monkeypatch):
    dynamixel_debug = load_dynamixel_debug(monkeypatch)
    QMessageBox.reset()

    widget = dynamixel_debug.DxlDebugWidget()
    widget.motor_controller = FakeMotorController()
    widget.chk_torque.setChecked(True)

    widget.begin_motor_limit_adjustment()

    assert widget.chk_torque.isChecked() is False
    assert widget.motor_controller.torque_calls[-2:] == [
        (dynamixel_debug.config.YAW_MOTOR_ID, False),
        (dynamixel_debug.config.PITCH_MOTOR_ID, False),
    ]


def test_read_current_limit_uses_motor_position(monkeypatch):
    dynamixel_debug = load_dynamixel_debug(monkeypatch)

    widget = dynamixel_debug.DxlDebugWidget()
    widget.motor_controller = FakeMotorController(yaw_steps=2222, pitch_steps=1888)

    widget.read_current_limit("yaw", "min")
    widget.read_current_limit("pitch", "max")

    assert widget.spin_yaw_min.value() == 2222
    assert widget.spin_pitch_max.value() == 1888


def test_prepare_limit_adjustment_rejects_connected_but_unready_motors(monkeypatch):
    dynamixel_debug = load_dynamixel_debug(monkeypatch)
    QMessageBox.reset()

    widget = dynamixel_debug.DxlDebugWidget()
    widget.motor_controller = FakeMotorController()
    widget.motor_controller.motors_ready = False
    widget.motor_controller.motor_error = "无法读取电机当前位置"

    started = widget.begin_motor_limit_adjustment()

    assert started is False
    assert "未就绪" in QMessageBox.warnings[-1][1]


def test_validate_motion_controller_uses_retry_ready_check_profile(monkeypatch):
    dynamixel_debug = load_dynamixel_debug(monkeypatch)

    widget = dynamixel_debug.DxlDebugWidget()
    widget.motor_controller = CapturingValidateMotorController()

    ready = widget._validate_motion_controller()

    assert ready is False
    assert widget.motor_controller.validate_calls == [
        {
            "motor_ids": (
                dynamixel_debug.config.YAW_MOTOR_ID,
                dynamixel_debug.config.PITCH_MOTOR_ID,
            ),
            "retries": 5,
            "initial_delay_sec": 0.2,
            "retry_delay_sec": 0.1,
        }
    ]


def test_toggle_connection_emits_controller_after_validation_reason_is_ready(monkeypatch):
    dynamixel_debug = load_dynamixel_debug(monkeypatch)
    QMessageBox.reset()

    class ReportingMotorController(CapturingValidateMotorController):
        pass

    monkeypatch.setattr(dynamixel_debug, "MotorController", ReportingMotorController)

    widget = dynamixel_debug.DxlDebugWidget()
    emitted = []
    widget.motor_connected.connect(lambda controller: emitted.append(controller))
    widget.btn_connect.setChecked(True)

    widget.toggle_connection()

    assert emitted
    assert emitted[0].motor_error == "无法 ping 通电机 ID 1：COMM_RX_TIMEOUT"
    assert "COMM_RX_TIMEOUT" in QMessageBox.warnings[-1][1]


def test_toggle_connection_starts_monitoring_even_when_initial_validation_fails(monkeypatch):
    dynamixel_debug = load_dynamixel_debug(monkeypatch)
    QMessageBox.reset()

    class ReportingMotorController(CapturingValidateMotorController):
        pass

    monkeypatch.setattr(dynamixel_debug, "MotorController", ReportingMotorController)

    widget = dynamixel_debug.DxlDebugWidget()
    widget.btn_connect.setChecked(True)

    widget.toggle_connection()

    assert widget.monitoring is True
    assert widget.timer.isActive() is True


def test_update_status_requires_consecutive_failures_before_marking_unready(monkeypatch):
    dynamixel_debug = load_dynamixel_debug(monkeypatch)
    monkeypatch.setattr(dynamixel_debug.config, "GUI_MOTOR_READY_FAIL_TICKS", 3, raising=False)

    widget = dynamixel_debug.DxlDebugWidget()
    widget.motor_controller = SequencedStatusMotorController(
        statuses={
            dynamixel_debug.config.YAW_MOTOR_ID: [None],
            dynamixel_debug.config.PITCH_MOTOR_ID: [build_status(1980)],
        },
        ready=True,
        error="",
    )
    emitted = []
    widget.motor_connected.connect(lambda controller: emitted.append(controller))

    widget.update_status()

    assert widget.motor_controller.motors_ready is True
    assert emitted == []


def test_update_status_requires_consecutive_successes_before_recovering_ready(monkeypatch):
    dynamixel_debug = load_dynamixel_debug(monkeypatch)
    monkeypatch.setattr(dynamixel_debug.config, "GUI_MOTOR_READY_RECOVER_TICKS", 2, raising=False)

    widget = dynamixel_debug.DxlDebugWidget()
    widget.motor_controller = SequencedStatusMotorController(
        statuses={
            dynamixel_debug.config.YAW_MOTOR_ID: [build_status(2100), build_status(2100)],
            dynamixel_debug.config.PITCH_MOTOR_ID: [build_status(1980), build_status(1980)],
        },
        ready=False,
        error="无法读取电机 ID 1 的状态。",
    )
    emitted = []
    widget.motor_connected.connect(lambda controller: emitted.append(controller))

    widget.update_status()
    assert widget.motor_controller.motors_ready is False
    assert emitted == []

    widget.update_status()

    assert widget.motor_controller.motors_ready is True
    assert emitted == [widget.motor_controller]


def test_update_status_recovers_after_initial_connection_validation_failed(monkeypatch):
    dynamixel_debug = load_dynamixel_debug(monkeypatch)
    monkeypatch.setattr(dynamixel_debug.config, "GUI_MOTOR_READY_RECOVER_TICKS", 2, raising=False)

    widget = dynamixel_debug.DxlDebugWidget()
    widget.motor_controller = SequencedStatusMotorController(
        statuses={
            dynamixel_debug.config.YAW_MOTOR_ID: [build_status(2100), build_status(2100)],
            dynamixel_debug.config.PITCH_MOTOR_ID: [build_status(1980), build_status(1980)],
        },
        ready=False,
        error="无法读取电机 ID 1 的当前位置：COMM_RX_TIMEOUT",
    )

    widget.start_monitoring()
    widget.update_status()
    widget.update_status()

    assert widget.motor_controller.motors_ready is True


def test_update_status_prefers_detailed_status_error_message_when_available(monkeypatch):
    dynamixel_debug = load_dynamixel_debug(monkeypatch)
    monkeypatch.setattr(dynamixel_debug.config, "GUI_MOTOR_READY_FAIL_TICKS", 1, raising=False)

    class DetailedErrorMotorController(SequencedStatusMotorController):
        def read_detailed_status_with_error(self, motor_id):
            if motor_id == dynamixel_debug.config.PITCH_MOTOR_ID:
                return None, "无法读取电机 ID 2 的当前位置：COMM_RX_TIMEOUT"
            return build_status(2100), ""

    widget = dynamixel_debug.DxlDebugWidget()
    widget.motor_controller = DetailedErrorMotorController(ready=True, error="")

    widget.update_status()

    assert widget.motor_controller.motors_ready is False
    assert widget.motor_controller.motor_error == "无法读取电机 ID 2 的当前位置：COMM_RX_TIMEOUT"


def test_toggle_connection_logs_probe_details_when_validation_fails(monkeypatch):
    dynamixel_debug = load_dynamixel_debug(monkeypatch)
    QMessageBox.reset()

    class ReportingMotorController(CapturingValidateMotorController):
        def probe_motor(self, motor_id):
            if motor_id == dynamixel_debug.config.PITCH_MOTOR_ID:
                return {
                    "motor_id": motor_id,
                    "ping_ok": True,
                    "model_number": 1234,
                    "present_position": None,
                    "failed_stage": "present_position",
                    "sdk_error": "COMM_RX_TIMEOUT",
                    "status_reads": {},
                }
            return {
                "motor_id": motor_id,
                "ping_ok": True,
                "model_number": 1234,
                "present_position": 2048,
                "failed_stage": "",
                "sdk_error": "",
                "status_reads": {},
            }

    monkeypatch.setattr(dynamixel_debug, "MotorController", ReportingMotorController)

    widget = dynamixel_debug.DxlDebugWidget()
    widget.btn_connect.setChecked(True)

    widget.toggle_connection()

    assert any("Probe ID 2" in line for line in widget.txt_alarm.lines)
    assert any("failed_stage=present_position" in line for line in widget.txt_alarm.lines)
    assert any("sdk_error=COMM_RX_TIMEOUT" in line for line in widget.txt_alarm.lines)


def test_update_status_logs_probe_details_when_monitor_read_fails(monkeypatch):
    dynamixel_debug = load_dynamixel_debug(monkeypatch)
    monkeypatch.setattr(dynamixel_debug.config, "GUI_MOTOR_READY_FAIL_TICKS", 1, raising=False)

    widget = dynamixel_debug.DxlDebugWidget()
    widget.motor_controller = ProbeReportingMotorController(
        statuses={
            dynamixel_debug.config.YAW_MOTOR_ID: [build_status(2100)],
            dynamixel_debug.config.PITCH_MOTOR_ID: [None],
        },
        probes={
            dynamixel_debug.config.PITCH_MOTOR_ID: {
                "motor_id": dynamixel_debug.config.PITCH_MOTOR_ID,
                "ping_ok": True,
                "model_number": 1234,
                "present_position": 1980,
                "failed_stage": "present_velocity",
                "sdk_error": "COMM_RX_TIMEOUT",
                "status_reads": {
                    "present_position": {
                        "address": 132,
                        "bytes": 4,
                        "ok": True,
                        "value": 1980,
                        "error": "",
                    },
                    "present_velocity": {
                        "address": 128,
                        "bytes": 4,
                        "ok": False,
                        "value": None,
                        "error": "COMM_RX_TIMEOUT",
                    },
                },
            }
        },
        ready=True,
        error="",
    )

    widget.update_status()

    assert widget.motor_controller.motors_ready is False
    assert any("Probe ID 2" in line for line in widget.txt_alarm.lines)
    assert any("failed_stage=present_velocity" in line for line in widget.txt_alarm.lines)
    assert any("present_position=1980" in line for line in widget.txt_alarm.lines)


def test_toggle_connection_applies_tracking_profile_from_config(monkeypatch):
    dynamixel_debug = load_dynamixel_debug(monkeypatch)

    class ProfiledMotorController(FakeMotorController):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.motors_ready = True
            self.motor_error = ""
            self.profile_calls = []

        def validate_motors(self, *_args, **_kwargs):
            self.motors_ready = True
            self.motor_error = ""
            return True

        def set_profile(self, motor_id, velocity, acceleration):
            self.profile_calls.append((motor_id, velocity, acceleration))

    monkeypatch.setattr(dynamixel_debug, "MotorController", ProfiledMotorController)
    monkeypatch.setattr(dynamixel_debug.config, "TRACKING_PROFILE_VELOCITY", 77, raising=False)
    monkeypatch.setattr(dynamixel_debug.config, "TRACKING_PROFILE_ACCELERATION", 88, raising=False)

    widget = dynamixel_debug.DxlDebugWidget()
    widget.btn_connect.setChecked(True)

    widget.toggle_connection()

    assert widget.motor_controller.profile_calls[-2:] == [
        (dynamixel_debug.config.YAW_MOTOR_ID, 77, 88),
        (dynamixel_debug.config.PITCH_MOTOR_ID, 77, 88),
    ]


def test_save_limits_rejects_when_tracking_start_pose_outside_range(monkeypatch):
    dynamixel_debug = load_dynamixel_debug(monkeypatch)
    limit_store = FakeMotorLimitStore()
    tracking_store = FakeTrackingStartStore(yaw=2300, pitch=1900)
    monkeypatch.setattr(dynamixel_debug, "motor_limit_store", lambda: limit_store)
    monkeypatch.setattr(dynamixel_debug, "tracking_start_pose_store", lambda: tracking_store)
    QMessageBox.reset()

    widget = dynamixel_debug.DxlDebugWidget()
    widget.spin_yaw_min.setValue(1800)
    widget.spin_yaw_max.setValue(2200)
    widget.spin_pitch_min.setValue(1700)
    widget.spin_pitch_max.setValue(2100)

    widget.save_motor_limits()

    assert limit_store.saved == []
    assert QMessageBox.warnings[-1][1].startswith("已保存的跟踪初始位超出")


def test_jog_clamps_to_saved_step_limits(monkeypatch):
    dynamixel_debug = load_dynamixel_debug(monkeypatch)
    limit_store = FakeMotorLimitStore(
        {
            "yaw_min_step": 100,
            "yaw_max_step": 105,
            "pitch_min_step": 0,
            "pitch_max_step": 4095,
        }
    )
    monkeypatch.setattr(dynamixel_debug, "motor_limit_store", lambda: limit_store)

    widget = dynamixel_debug.DxlDebugWidget()
    widget.motor_controller = FakeMotorController(yaw_steps=100, pitch_steps=2048)

    widget.jog(dynamixel_debug.config.YAW_MOTOR_ID, 1)

    assert widget.motor_controller.goal_positions[-1] == {
        dynamixel_debug.config.YAW_MOTOR_ID: 105
    }
