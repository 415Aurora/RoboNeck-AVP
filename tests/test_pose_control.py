import importlib
import os
import sys
import types

import numpy as np
import pytest


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)


from src.core.controller import ControlState, ControllerResult, HeadPoseSample


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
        self._visible = True
        self._enabled = True
        self._tooltip = ""
        self._style = ""

    def setLayout(self, layout):
        self._layout = layout

    def setVisible(self, visible):
        self._visible = bool(visible)

    def isVisible(self):
        return self._visible

    def setEnabled(self, enabled):
        self._enabled = bool(enabled)

    def isEnabled(self):
        return self._enabled

    def setToolTip(self, text):
        self._tooltip = text

    def setWordWrap(self, _enabled):
        return None

    def setStyleSheet(self, value):
        self._style = value


class QGroupBox(QWidget):
    pass


class Layout:
    def __init__(self, *args, **kwargs):
        self.items = []

    def addWidget(self, widget, *args):
        self.items.append(("widget", widget, args))

    def addLayout(self, layout, *args):
        self.items.append(("layout", layout, args))

    def addStretch(self):
        self.items.append(("stretch",))


class QFormLayout(Layout):
    def addRow(self, *items):
        self.items.append(("row", items))


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


class QPushButton(QWidget):
    def __init__(self, text=""):
        super().__init__()
        self._text = text
        self._checkable = False
        self._checked = False
        self._signals_blocked = False
        self.toggled = Signal()
        self.clicked = Signal()

    def setCheckable(self, value):
        self._checkable = value

    def setStyleSheet(self, value):
        self._style = value

    def setFlat(self, value):
        self._flat = value

    def setText(self, text):
        self._text = text

    def text(self):
        return self._text

    def isChecked(self):
        return self._checked

    def setChecked(self, value):
        changed = self._checked != value
        self._checked = value
        if changed and not self._signals_blocked:
            self.toggled.emit(value)

    def click(self):
        self.clicked.emit()
        if self._checkable:
            self.setChecked(not self._checked)

    def blockSignals(self, blocked):
        previous = self._signals_blocked
        self._signals_blocked = blocked
        return previous


class QCheckBox(QWidget):
    pass


class QToolButton(QPushButton):
    def setArrowType(self, arrow_type):
        self._arrow_type = arrow_type


class QComboBox(QWidget):
    def __init__(self):
        super().__init__()
        self._items = []
        self._index = -1
        self.currentIndexChanged = Signal()

    def addItem(self, text, user_data=None):
        self._items.append((text, user_data))
        if self._index == -1:
            self.setCurrentIndex(0)

    def addItems(self, texts):
        for text in texts:
            self.addItem(text, text)

    def setCurrentIndex(self, index):
        changed = self._index != index
        self._index = index
        if changed:
            self.currentIndexChanged.emit(index)

    def currentIndex(self):
        return self._index

    def currentData(self):
        if self._index < 0:
            return None
        return self._items[self._index][1]

    def findData(self, user_data):
        for index, (_text, data) in enumerate(self._items):
            if data == user_data:
                return index
        return -1

    def setToolTip(self, text):
        self._tooltip = text


class QSpinBox(QWidget):
    def __init__(self):
        super().__init__()
        self._value = 0

    def setRange(self, minimum, maximum):
        self._range = (minimum, maximum)

    def setValue(self, value):
        self._value = value

    def value(self):
        return self._value

    def setToolTip(self, text):
        self._tooltip = text

    def setDecimals(self, decimals):
        self._decimals = decimals

    def setSingleStep(self, step):
        self._single_step = step


class QDoubleSpinBox(QSpinBox):
    pass


class QMessageBox:
    class Icon:
        Information = 1

    class StandardButton:
        Ok = 1
        Cancel = 2

    next_exec_result = StandardButton.Ok
    infos = []
    warnings = []

    def __init__(self):
        self._title = ""
        self._text = ""

    def setWindowTitle(self, title):
        self._title = title

    def setText(self, text):
        self._text = text

    def setIcon(self, icon):
        self._icon = icon

    def setStandardButtons(self, buttons):
        self._buttons = buttons

    def exec(self):
        return self.next_exec_result

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


def pyqtSignal(*_args, **_kwargs):
    return Signal()


def load_pose_control(monkeypatch):
    pyqt6 = types.ModuleType("PyQt6")
    qtwidgets = types.ModuleType("PyQt6.QtWidgets")
    qtcore = types.ModuleType("PyQt6.QtCore")

    qtwidgets.QWidget = QWidget
    qtwidgets.QGroupBox = QGroupBox
    qtwidgets.QVBoxLayout = QVBoxLayout
    qtwidgets.QFormLayout = QFormLayout
    qtwidgets.QGridLayout = QGridLayout
    qtwidgets.QLabel = QLabel
    qtwidgets.QPushButton = QPushButton
    qtwidgets.QToolButton = QToolButton
    qtwidgets.QCheckBox = QCheckBox
    qtwidgets.QComboBox = QComboBox
    qtwidgets.QHBoxLayout = QHBoxLayout
    qtwidgets.QMessageBox = QMessageBox
    qtwidgets.QSpinBox = QSpinBox
    qtwidgets.QDoubleSpinBox = QDoubleSpinBox

    class ArrowTypeNamespace:
        RightArrow = "right"
        DownArrow = "down"

    QtNamespace = type("QtNamespace", (), {"ArrowType": ArrowTypeNamespace})

    qtcore.Qt = QtNamespace
    qtcore.QTimer = QTimer
    qtcore.pyqtSignal = pyqtSignal

    monkeypatch.setitem(sys.modules, "PyQt6", pyqt6)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", qtcore)
    sys.modules.pop("src.gui.pose_control", None)
    return importlib.import_module("src.gui.pose_control")


class FakeRetargeter:
    def __init__(self):
        self.sync_calls = []
        self.resync_calls = 0
        self.compute_result = (0.0, 0.0)
        self.base_imu_compensation_mode = "off"

    def sync_to_robot_pose(self, head_pose_mat, robot_pose, base_imu_rpy=None):
        self.sync_calls.append((head_pose_mat, robot_pose, base_imu_rpy))

    def request_resync(self):
        self.resync_calls += 1

    def reset_calibration(self):
        self.resync_calls += 1

    def compute_neck_target(self, head_pose_mat, base_imu_rpy=None):
        return self.compute_result

    def set_base_imu_compensation_mode(self, mode):
        self.base_imu_compensation_mode = mode


class FakeMotorController:
    def __init__(self, yaw_steps=2048, pitch_steps=2048, connected=True):
        self.connected = connected
        self.positions = {1: yaw_steps, 2: pitch_steps}
        self.goal_positions = []
        self.torque_calls = []
        self.motors_ready = True
        self.motor_error = ""

    def get_present_position(self, motor_id):
        return self.positions[motor_id]

    def set_goal_positions(self, commands):
        self.goal_positions.append(dict(commands))
        self.positions.update(commands)

    def enable_torque(self, motor_id, enable=True):
        self.torque_calls.append((motor_id, enable))


class TorqueResultMotorController(FakeMotorController):
    def __init__(self, torque_results=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.torque_results = dict(torque_results or {})

    def enable_torque(self, motor_id, enable=True):
        self.torque_calls.append((motor_id, enable))
        return self.torque_results.get((motor_id, enable), (True, ""))


class SettlingMotorController(FakeMotorController):
    def __init__(self, yaw_steps=2048, pitch_steps=2048, connected=True, yaw_offset=-4, pitch_offset=3):
        super().__init__(yaw_steps=yaw_steps, pitch_steps=pitch_steps, connected=connected)
        self.yaw_offset = yaw_offset
        self.pitch_offset = pitch_offset

    def set_goal_positions(self, commands):
        self.goal_positions.append(dict(commands))
        for motor_id, target in commands.items():
            if motor_id == 1:
                self.positions[motor_id] = int(target) + self.yaw_offset
            elif motor_id == 2:
                self.positions[motor_id] = int(target) + self.pitch_offset
            else:
                self.positions[motor_id] = int(target)


class FakeAVPClient:
    def __init__(self, pose_matrix, base_imu, sample=None, pose_status=None):
        self.pose_matrix = pose_matrix
        self.base_imu = base_imu
        self.sample = sample
        self.pose_status = pose_status or {
            "valid": sample is not None or pose_matrix is not None,
            "reason": "",
            "fresh": sample is not None,
        }
        self.sample_calls = 0
        self.matrix_calls = 0

    def get_latest_head_pose_sample(self, now=None):
        self.sample_calls += 1
        return self.sample

    def get_latest_head_pose_matrix(self):
        self.matrix_calls += 1
        return self.pose_matrix

    def get_camera_imu(self):
        return self.base_imu

    def get_pose_status(self):
        return dict(self.pose_status)


class FakeTrackingStartStore:
    def __init__(self, yaw=2048, pitch=2048):
        self.loaded = {"yaw_start_step": yaw, "pitch_start_step": pitch}
        self.saved = []

    def load(self):
        return dict(self.loaded)

    def save(self, yaw_start_step, pitch_start_step):
        payload = {
            "yaw_start_step": int(yaw_start_step),
            "pitch_start_step": int(pitch_start_step),
        }
        self.loaded = dict(payload)
        self.saved.append(dict(payload))
        return payload


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


def drain_homing(widget, max_ticks=64):
    ticks = 0
    while getattr(widget, "_homing_active", False) and ticks < max_ticks:
        widget._homing_timer.timeout.emit()
        ticks += 1
    return ticks


def make_head_pose_sample(pose_matrix=None, base_imu=(0.0, 0.0, 0.0), timestamp=1.0):
    return HeadPoseSample(
        head_pose_matrix=np.eye(4) if pose_matrix is None else pose_matrix,
        timestamp=timestamp,
        base_imu_rpy=base_imu,
        raw_payload={"fresh": True},
        fresh=True,
        source_timestamp=timestamp,
    )


def prime_tracking_runtime(widget, pose_control):
    positions = {
        pose_control.config.YAW_MOTOR_ID: widget.motor_controller.positions[pose_control.config.YAW_MOTOR_ID],
        pose_control.config.PITCH_MOTOR_ID: widget.motor_controller.positions[pose_control.config.PITCH_MOTOR_ID],
    }
    widget.spin_home_yaw.setValue(positions[pose_control.config.YAW_MOTOR_ID])
    widget.spin_home_pitch.setValue(positions[pose_control.config.PITCH_MOTOR_ID])
    widget.runtime.update_tracking_start_positions(widget._tracking_start_positions())
    widget.runtime.auto_track_after_sync = True
    widget.runtime.mode = ControlState.TRACKING
    widget.runtime.controller.robot_synced = True
    widget.runtime.controller.last_commands = dict(positions)
    widget.runtime.controller.last_hold_commands = dict(positions)
    widget.runtime.last_result = ControllerResult(
        state=ControlState.TRACKING,
        commands=dict(positions),
        reason="tracking",
        hold_position=dict(positions),
    )


def test_toggle_tracking_uses_startup_sequence_when_stream_is_ready(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    monkeypatch.setattr(pose_control.time, "sleep", lambda _seconds: None)
    widget = pose_control.PoseControlWidget()
    widget.retargeter = FakeRetargeter()
    widget.motor_controller = FakeMotorController(yaw_steps=2148, pitch_steps=1998)
    widget.avp_client = FakeAVPClient(np.eye(4), (0.11, -0.07, 0.0))
    widget.set_streaming_ready(True)

    widget.toggle_tracking(True)
    drain_homing(widget)

    assert len(widget.retargeter.sync_calls) == 1
    _pose_mat, robot_pose, base_imu = widget.retargeter.sync_calls[0]
    assert robot_pose == (0.0, 0.0)
    assert base_imu == (0.11, -0.07, 0.0)
    assert widget.is_tracking is True


def test_calibrate_moves_home_then_syncs_zero_pose_and_restarts_tracking(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    QMessageBox.next_exec_result = QMessageBox.StandardButton.Ok
    monkeypatch.setattr(pose_control.time, "sleep", lambda _seconds: None)
    widget = pose_control.PoseControlWidget()
    widget.retargeter = FakeRetargeter()
    widget.motor_controller = FakeMotorController(connected=True)
    widget.avp_client = FakeAVPClient(np.eye(4), (0.01, 0.02, 0.0))
    widget.spin_home_yaw.setValue(2100)
    widget.spin_home_pitch.setValue(1980)

    widget.calibrate()
    drain_homing(widget)

    assert widget.motor_controller.goal_positions[0] == {
        pose_control.config.YAW_MOTOR_ID: 2100,
        pose_control.config.PITCH_MOTOR_ID: 1984,
    }
    assert widget.motor_controller.goal_positions[-1] == {
        pose_control.config.YAW_MOTOR_ID: 2100,
        pose_control.config.PITCH_MOTOR_ID: 1984,
    }
    assert len(widget.retargeter.sync_calls) == 1
    _pose_mat, robot_pose, base_imu = widget.retargeter.sync_calls[0]
    assert robot_pose == (0.0, 0.0)
    assert base_imu == (0.01, 0.02, 0.0)
    assert widget.is_tracking is True


def test_toggle_tracking_refuses_to_start_when_stream_is_not_ready(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    widget = pose_control.PoseControlWidget()
    widget.retargeter = FakeRetargeter()
    widget.motor_controller = FakeMotorController()
    widget.avp_client = FakeAVPClient(np.eye(4), (0.0, 0.0, 0.0))

    widget.toggle_tracking(True)

    assert widget.is_tracking is False
    assert widget.retargeter.sync_calls == []
    assert QMessageBox.warnings[-1][1].startswith("Video stream")


def test_start_tracking_sequence_recenters_before_sync_and_tracking(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    monkeypatch.setattr(pose_control.time, "sleep", lambda _seconds: None)

    widget = pose_control.PoseControlWidget()
    widget.retargeter = FakeRetargeter()
    widget.motor_controller = FakeMotorController(yaw_steps=2148, pitch_steps=1998)
    widget.avp_client = FakeAVPClient(np.eye(4), (0.03, -0.04, 0.0))
    widget.set_streaming_ready(True)
    widget.spin_home_yaw.setValue(pose_control.config.ZERO_POS)
    widget.spin_home_pitch.setValue(pose_control.config.ZERO_POS)

    started = widget.start_tracking_sequence()
    drain_homing(widget)

    assert started is True
    assert widget.motor_controller.goal_positions[0] == {
        pose_control.config.YAW_MOTOR_ID: 2084,
        pose_control.config.PITCH_MOTOR_ID: 2048,
    }
    assert widget.motor_controller.goal_positions[-1] == {
        pose_control.config.YAW_MOTOR_ID: pose_control.config.ZERO_POS,
        pose_control.config.PITCH_MOTOR_ID: pose_control.config.ZERO_POS,
    }
    assert widget.retargeter.sync_calls[-1][1] == (0.0, 0.0)
    assert widget.is_tracking is True


def test_control_loop_clamps_tracking_targets_to_motor_limits(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    limit_store = FakeMotorLimitStore(
        {
            "yaw_min_step": 2030,
            "yaw_max_step": 2060,
            "pitch_min_step": 2020,
            "pitch_max_step": 2055,
        }
    )
    monkeypatch.setattr(pose_control, "motor_limit_store", lambda: limit_store)
    widget = pose_control.PoseControlWidget()
    widget.retargeter = FakeRetargeter()
    widget.retargeter.compute_result = (np.deg2rad(90.0), np.deg2rad(-90.0))
    widget.motor_controller = FakeMotorController()
    widget.avp_client = FakeAVPClient(np.eye(4), (0.0, 0.0, 0.0))
    widget.spin_home_yaw.setValue(pose_control.config.ZERO_POS)
    widget.spin_home_pitch.setValue(pose_control.config.ZERO_POS)
    widget.runtime.update_tracking_start_positions(widget._tracking_start_positions())
    widget.is_tracking = True

    widget.control_loop()

    assert widget.motor_controller.goal_positions[-1] == {
        pose_control.config.YAW_MOTOR_ID: 2060,
        pose_control.config.PITCH_MOTOR_ID: 2020,
    }


def test_control_loop_prefers_head_pose_sample_over_raw_matrix(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    widget = pose_control.PoseControlWidget()
    widget.retargeter = FakeRetargeter()
    widget.retargeter.compute_result = (np.deg2rad(8.0), np.deg2rad(-4.0))
    widget.motor_controller = FakeMotorController()
    widget.avp_client = FakeAVPClient(
        pose_matrix=None,
        base_imu=(0.2, -0.1, 0.0),
        sample=make_head_pose_sample(base_imu=(0.2, -0.1, 0.0)),
    )
    widget.spin_home_yaw.setValue(pose_control.config.ZERO_POS)
    widget.spin_home_pitch.setValue(pose_control.config.ZERO_POS)
    widget.runtime.update_tracking_start_positions(widget._tracking_start_positions())
    widget.is_tracking = True

    widget.control_loop()

    assert widget.avp_client.sample_calls == 1
    assert widget.avp_client.matrix_calls == 0
    assert widget.motor_controller.goal_positions


def test_control_loop_skips_motor_update_when_pose_sample_is_invalid(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    widget = pose_control.PoseControlWidget()
    widget.retargeter = FakeRetargeter()
    widget.motor_controller = FakeMotorController()
    widget.avp_client = FakeAVPClient(
        pose_matrix=None,
        base_imu=(0.0, 0.0, 0.0),
        sample=None,
        pose_status={"valid": False, "reason": "invalid_head_shape", "fresh": False},
    )
    widget.is_tracking = True

    widget.control_loop()

    assert widget.motor_controller.goal_positions == []
    assert widget.lbl_head_yaw.text() == "0.0°"
    assert widget.lbl_head_pitch.text() == "0.0°"


def test_start_tracking_sequence_reports_pose_reason_when_sync_sample_is_invalid(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    monkeypatch.setattr(pose_control.time, "sleep", lambda _seconds: None)
    QMessageBox.reset()
    widget = pose_control.PoseControlWidget()
    widget.retargeter = FakeRetargeter()
    widget.motor_controller = FakeMotorController()
    widget.avp_client = FakeAVPClient(
        pose_matrix=None,
        base_imu=None,
        sample=None,
        pose_status={"valid": False, "reason": "missing_head_field", "fresh": False},
    )
    widget.set_streaming_ready(True)

    widget.start_tracking_sequence()
    drain_homing(widget)

    assert widget.is_tracking is False
    assert "头姿字段" in QMessageBox.warnings[-1][1]


def test_build_pose_unavailable_message_maps_streamer_initializing_to_actionable_hint(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    widget = pose_control.PoseControlWidget()
    widget.avp_client = FakeAVPClient(
        pose_matrix=None,
        base_imu=None,
        sample=None,
        pose_status={"valid": False, "reason": "streamer_initializing", "fresh": False, "state_age_sec": 4.8},
    )

    message = widget._build_pose_unavailable_message("当前没有可用的 AVP 头部姿态数据。")

    assert "Tracking Streamer" in message
    assert "Start" in message
    assert "4.8s" in message


def test_start_tracking_sequence_allows_sync_without_imu_when_compensation_is_off(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    monkeypatch.setattr(pose_control.time, "sleep", lambda _seconds: None)
    widget = pose_control.PoseControlWidget()
    widget.retargeter = FakeRetargeter()
    widget.motor_controller = FakeMotorController()
    widget.avp_client = FakeAVPClient(
        pose_matrix=None,
        base_imu=None,
        sample=make_head_pose_sample(base_imu=None),
    )
    widget.set_streaming_ready(True)

    started = widget.start_tracking_sequence()
    drain_homing(widget)

    assert started is True
    assert widget.is_tracking is True
    assert widget.retargeter.sync_calls[-1][2] is None


def test_control_loop_holds_when_pose_sample_is_not_fresh(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    widget = pose_control.PoseControlWidget()
    widget.retargeter = FakeRetargeter()
    widget.retargeter.compute_result = (np.deg2rad(8.0), np.deg2rad(-4.0))
    widget.motor_controller = FakeMotorController()
    stale_sample = make_head_pose_sample(base_imu=(0.0, 0.0, 0.0))
    stale_sample.fresh = False
    stale_sample.raw_payload["fresh"] = False
    widget.avp_client = FakeAVPClient(
        pose_matrix=None,
        base_imu=(0.0, 0.0, 0.0),
        sample=stale_sample,
        pose_status={"valid": True, "reason": "stale_sample", "fresh": False},
    )
    widget.is_tracking = True
    prime_tracking_runtime(widget, pose_control)
    expected_hold = dict(widget.runtime.controller.last_commands)

    widget.control_loop()

    assert widget.motor_controller.goal_positions[-1] == expected_hold
    assert widget.is_tracking is True
    assert getattr(widget, "is_tracking_paused", False) is True


def test_control_loop_enters_pause_and_holds_last_command_when_sample_turns_stale(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    widget = pose_control.PoseControlWidget()
    widget.retargeter = FakeRetargeter()
    widget.retargeter.compute_result = (np.deg2rad(6.0), np.deg2rad(-3.0))
    widget.motor_controller = FakeMotorController()
    fresh_sample = make_head_pose_sample(base_imu=(0.0, 0.0, 0.0), timestamp=1.0)
    stale_sample = make_head_pose_sample(base_imu=(0.0, 0.0, 0.0), timestamp=1.1)
    stale_sample.fresh = False
    stale_sample.raw_payload["fresh"] = False
    widget.avp_client = FakeAVPClient(
        pose_matrix=None,
        base_imu=(0.0, 0.0, 0.0),
        sample=fresh_sample,
        pose_status={"valid": True, "reason": "", "fresh": True},
    )
    widget.is_tracking = True
    widget.pose_initialized = True
    widget.motor_initialized = True
    prime_tracking_runtime(widget, pose_control)

    widget.control_loop()
    last_command = dict(widget.motor_controller.goal_positions[-1])

    widget.avp_client.sample = stale_sample
    widget.avp_client.pose_status = {"valid": False, "reason": "stale_sample", "fresh": False}
    widget.control_loop()

    status = widget.runtime.get_status()
    assert widget.is_tracking is True
    assert widget.is_tracking_paused is True
    assert status.tracking_active is True
    assert status.tracking_paused is True
    assert status.reason == "stale_sample"
    assert widget.motor_controller.goal_positions[-1] == last_command


def test_control_loop_stays_paused_until_explicit_resync_when_pose_becomes_valid_again(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    widget = pose_control.PoseControlWidget()
    widget.retargeter = FakeRetargeter()
    widget.retargeter.compute_result = (np.deg2rad(6.0), np.deg2rad(-3.0))
    widget.motor_controller = FakeMotorController()
    stale_sample = make_head_pose_sample(base_imu=(0.0, 0.0, 0.0), timestamp=1.0)
    stale_sample.fresh = False
    stale_sample.raw_payload["fresh"] = False
    fresh_sample = make_head_pose_sample(base_imu=(0.0, 0.0, 0.0), timestamp=1.1)
    widget.avp_client = FakeAVPClient(
        pose_matrix=None,
        base_imu=(0.0, 0.0, 0.0),
        sample=stale_sample,
        pose_status={"valid": False, "reason": "stale_sample", "fresh": False},
    )
    widget.is_tracking = True
    widget.pose_initialized = True
    widget.motor_initialized = True
    prime_tracking_runtime(widget, pose_control)

    widget.control_loop()

    assert widget.is_tracking_paused is True

    widget.avp_client.sample = fresh_sample
    widget.avp_client.pose_status = {"valid": True, "reason": "", "fresh": True}
    widget.control_loop()

    status = widget.runtime.get_status()
    assert widget.is_tracking is True
    assert widget.is_tracking_paused is True
    assert status.tracking_paused is True
    assert status.tracking_active is True
    assert status.reason == "resync_required"


def test_pose_widget_emits_runtime_events_for_pause_and_resume(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    widget = pose_control.PoseControlWidget()
    widget.retargeter = FakeRetargeter()
    widget.retargeter.compute_result = (np.deg2rad(6.0), np.deg2rad(-3.0))
    widget.motor_controller = FakeMotorController()
    fresh_sample = make_head_pose_sample(base_imu=(0.0, 0.0, 0.0), timestamp=1.0)
    stale_sample = make_head_pose_sample(base_imu=(0.0, 0.0, 0.0), timestamp=1.1)
    stale_sample.fresh = False
    stale_sample.raw_payload["fresh"] = False
    widget.avp_client = FakeAVPClient(
        pose_matrix=None,
        base_imu=(0.0, 0.0, 0.0),
        sample=fresh_sample,
        pose_status={"valid": True, "reason": "", "fresh": True},
    )
    widget.is_tracking = True
    widget.pose_initialized = True
    widget.motor_initialized = True
    prime_tracking_runtime(widget, pose_control)
    events = []
    widget.runtime_event.connect(lambda level, message: events.append((level, message)))

    widget.control_loop()
    widget.avp_client.sample = stale_sample
    widget.avp_client.pose_status = {"valid": False, "reason": "stale_sample", "fresh": False}
    widget.control_loop()
    widget.avp_client.sample = fresh_sample
    widget.avp_client.pose_status = {"valid": True, "reason": "", "fresh": True}
    widget.control_loop()

    assert any(level == "warning" and "[AVP] POSE_INVALID" in message for level, message in events)
    assert any(level == "warning" and "[TRACK] PAUSED" in message and "reason=stale_sample" in message for level, message in events)
    assert any(level == "info" and "[TRACK] RESYNC_BEGIN" in message for level, message in events)
    assert not any(level == "info" and "[TRACK] RESUMED" in message for level, message in events)


def test_pose_widget_loads_saved_tracking_start_pose(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    store = FakeTrackingStartStore(yaw=2333, pitch=1777)
    monkeypatch.setattr(pose_control, "tracking_start_pose_store", lambda: store)

    widget = pose_control.PoseControlWidget()

    assert widget.spin_home_yaw.value() == 2333
    assert widget.spin_home_pitch.value() == 1777


def test_save_tracking_start_pose_persists_manual_spin_values(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    store = FakeTrackingStartStore()
    monkeypatch.setattr(pose_control, "tracking_start_pose_store", lambda: store)
    QMessageBox.reset()

    widget = pose_control.PoseControlWidget()
    widget.spin_home_yaw.setValue(2360)
    widget.spin_home_pitch.setValue(1750)

    widget.save_tracking_start_pose()

    assert store.saved[-1] == {"yaw_start_step": 2360, "pitch_start_step": 1750}
    assert "跟踪初始位" in QMessageBox.infos[-1][1]


def test_begin_tracking_start_pose_adjustment_disables_torque_for_both_axes(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    QMessageBox.reset()
    widget = pose_control.PoseControlWidget()
    widget.motor_controller = FakeMotorController()
    widget.is_tracking = True

    widget.begin_tracking_start_pose_adjustment()

    assert widget.is_tracking is False
    assert widget._tracking_start_adjustment_active is True
    assert widget.motor_controller.torque_calls == [
        (pose_control.config.YAW_MOTOR_ID, False),
        (pose_control.config.PITCH_MOTOR_ID, False),
    ]


def test_begin_tracking_start_pose_adjustment_allows_connected_but_unready_motors(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    QMessageBox.reset()
    widget = pose_control.PoseControlWidget()
    widget.motor_controller = FakeMotorController()
    widget.motor_controller.motors_ready = False
    widget.motor_controller.motor_error = "无法读取电机 ID 2 的状态。"

    started = widget.begin_tracking_start_pose_adjustment()

    assert started is True
    assert widget._tracking_start_adjustment_active is True
    assert widget.motor_controller.torque_calls == [
        (pose_control.config.YAW_MOTOR_ID, False),
        (pose_control.config.PITCH_MOTOR_ID, False),
    ]
    assert "已尽力关闭扭矩" in QMessageBox.warnings[-1][1]
    assert "ID 2" in QMessageBox.warnings[-1][1]


def test_begin_tracking_start_pose_adjustment_warns_when_only_one_axis_torque_disable_succeeds(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    QMessageBox.reset()
    widget = pose_control.PoseControlWidget()
    widget.motor_controller = TorqueResultMotorController(
        torque_results={
            (pose_control.config.YAW_MOTOR_ID, False): (True, ""),
            (pose_control.config.PITCH_MOTOR_ID, False): (False, "无法关闭电机 ID 2 的扭矩：COMM_RX_TIMEOUT"),
        }
    )
    widget.motor_controller.motors_ready = False
    widget.motor_controller.motor_error = "无法读取电机 ID 2 的状态。"

    started = widget.begin_tracking_start_pose_adjustment()

    assert started is True
    assert widget._tracking_start_adjustment_active is True
    assert "俯仰轴" in QMessageBox.warnings[-1][1]
    assert "COMM_RX_TIMEOUT" in QMessageBox.warnings[-1][1]


def test_begin_tracking_start_pose_adjustment_rejects_when_all_axes_torque_disable_fail(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    QMessageBox.reset()
    widget = pose_control.PoseControlWidget()
    widget.motor_controller = TorqueResultMotorController(
        torque_results={
            (pose_control.config.YAW_MOTOR_ID, False): (False, "无法关闭电机 ID 1 的扭矩：COMM_RX_TIMEOUT"),
            (pose_control.config.PITCH_MOTOR_ID, False): (False, "无法关闭电机 ID 2 的扭矩：COMM_RX_TIMEOUT"),
        }
    )
    widget.motor_controller.motors_ready = False
    widget.motor_controller.motor_error = "无法读取电机 ID 2 的状态。"

    started = widget.begin_tracking_start_pose_adjustment()

    assert started is False
    assert widget._tracking_start_adjustment_active is False
    assert "无法进入初始位手动设置模式" in QMessageBox.warnings[-1][1]
    assert "COMM_RX_TIMEOUT" in QMessageBox.warnings[-1][1]


def test_read_tracking_start_pose_from_motors_updates_both_spinboxes(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    widget = pose_control.PoseControlWidget()
    widget.motor_controller = FakeMotorController(yaw_steps=2310, pitch_steps=1810)

    widget.read_tracking_start_pose_from_motors()

    assert widget.spin_home_yaw.value() == 2310
    assert widget.spin_home_pitch.value() == 1810


def test_save_tracking_start_pose_reenables_torque_after_adjustment(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    store = FakeTrackingStartStore()
    monkeypatch.setattr(pose_control, "tracking_start_pose_store", lambda: store)
    QMessageBox.reset()

    widget = pose_control.PoseControlWidget()
    widget.motor_controller = FakeMotorController()
    widget.begin_tracking_start_pose_adjustment()
    widget.spin_home_yaw.setValue(2370)
    widget.spin_home_pitch.setValue(1740)

    widget.save_tracking_start_pose()

    assert store.saved[-1] == {"yaw_start_step": 2370, "pitch_start_step": 1740}
    assert widget._tracking_start_adjustment_active is False
    assert widget.motor_controller.torque_calls[-2:] == [
        (pose_control.config.YAW_MOTOR_ID, True),
        (pose_control.config.PITCH_MOTOR_ID, True),
    ]


def test_save_tracking_start_pose_warns_when_reenable_torque_partially_fails(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    store = FakeTrackingStartStore()
    monkeypatch.setattr(pose_control, "tracking_start_pose_store", lambda: store)
    QMessageBox.reset()

    widget = pose_control.PoseControlWidget()
    widget.motor_controller = TorqueResultMotorController(
        torque_results={
            (pose_control.config.YAW_MOTOR_ID, False): (True, ""),
            (pose_control.config.PITCH_MOTOR_ID, False): (True, ""),
            (pose_control.config.YAW_MOTOR_ID, True): (True, ""),
            (pose_control.config.PITCH_MOTOR_ID, True): (False, "无法使能电机 ID 2 的扭矩：COMM_RX_TIMEOUT"),
        }
    )

    widget.begin_tracking_start_pose_adjustment()
    widget.spin_home_yaw.setValue(2370)
    widget.spin_home_pitch.setValue(1740)

    saved = widget.save_tracking_start_pose()

    assert saved is True
    assert widget._tracking_start_adjustment_active is False
    assert "重新上扭矩" in QMessageBox.warnings[-1][1]
    assert "COMM_RX_TIMEOUT" in QMessageBox.warnings[-1][1]


def test_save_tracking_start_pose_rejects_values_outside_motor_limits(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    start_store = FakeTrackingStartStore()
    limit_store = FakeMotorLimitStore(
        {
            "yaw_min_step": 1800,
            "yaw_max_step": 2200,
            "pitch_min_step": 1700,
            "pitch_max_step": 2100,
        }
    )
    monkeypatch.setattr(pose_control, "tracking_start_pose_store", lambda: start_store)
    monkeypatch.setattr(pose_control, "motor_limit_store", lambda: limit_store)
    QMessageBox.reset()

    widget = pose_control.PoseControlWidget()
    widget.spin_home_yaw.setValue(2300)
    widget.spin_home_pitch.setValue(1900)

    widget.save_tracking_start_pose()

    assert start_store.saved == []
    assert QMessageBox.warnings[-1][1].startswith("跟踪初始位超出")


def test_move_to_tracking_start_pose_refuses_saved_pose_outside_motor_limits(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    monkeypatch.setattr(pose_control.time, "sleep", lambda _seconds: None)
    limit_store = FakeMotorLimitStore(
        {
            "yaw_min_step": 1800,
            "yaw_max_step": 2200,
            "pitch_min_step": 1700,
            "pitch_max_step": 2100,
        }
    )
    monkeypatch.setattr(pose_control, "motor_limit_store", lambda: limit_store)
    QMessageBox.reset()

    widget = pose_control.PoseControlWidget()
    widget.retargeter = FakeRetargeter()
    widget.motor_controller = FakeMotorController(yaw_steps=2148, pitch_steps=1998)
    widget.spin_home_yaw.setValue(2300)
    widget.spin_home_pitch.setValue(1980)

    moved = widget.move_to_tracking_start_pose()

    assert moved is False
    assert widget.motor_controller.goal_positions == []
    assert QMessageBox.warnings[-1][1].startswith("跟踪初始位超出")


def test_move_to_tracking_start_pose_rejects_connected_but_unready_motors(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    QMessageBox.reset()

    widget = pose_control.PoseControlWidget()
    widget.motor_controller = FakeMotorController(yaw_steps=2148, pitch_steps=1998, connected=True)
    widget.motor_controller.motors_ready = False
    widget.motor_controller.motor_error = "无法读取电机当前位置"
    widget.spin_home_yaw.setValue(2100)
    widget.spin_home_pitch.setValue(1980)

    moved = widget.move_to_tracking_start_pose()

    assert moved is False
    assert widget.motor_controller.goal_positions == []
    assert "未就绪" in QMessageBox.warnings[-1][1]


def test_pose_widget_applies_default_base_imu_compensation_mode_from_config(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    monkeypatch.setattr(pose_control.config, "ZED_IMU_COMPENSATION_MODE", "off", raising=False)

    widget = pose_control.PoseControlWidget()

    assert widget.retargeter.base_imu_compensation_mode == "off"
    assert widget.combo_imu_compensation.currentData() == "off"


def test_pose_widget_updates_retargeter_when_compensation_mode_changes(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    widget = pose_control.PoseControlWidget()
    widget.retargeter = FakeRetargeter()

    index = widget.combo_imu_compensation.findData("yaw_pitch")
    widget.combo_imu_compensation.setCurrentIndex(index)

    assert widget.retargeter.base_imu_compensation_mode == "yaw_pitch"


def test_move_to_tracking_start_pose_moves_to_saved_pose_without_sync(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    monkeypatch.setattr(pose_control.time, "sleep", lambda _seconds: None)

    widget = pose_control.PoseControlWidget()
    widget.retargeter = FakeRetargeter()
    widget.motor_controller = FakeMotorController(yaw_steps=2148, pitch_steps=1998)
    widget.spin_home_yaw.setValue(2100)
    widget.spin_home_pitch.setValue(1980)

    moved = widget.move_to_tracking_start_pose()
    drain_homing(widget)

    assert moved is True
    assert widget.motor_controller.goal_positions[-1] == {
        pose_control.config.YAW_MOTOR_ID: 2100,
        pose_control.config.PITCH_MOTOR_ID: 1980,
    }
    assert widget.retargeter.sync_calls == []
    assert widget.is_tracking is False


def test_move_to_tracking_start_pose_succeeds_when_motor_settles_within_step_tolerance(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    monkeypatch.setattr(pose_control.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(pose_control.config, "CENTERING_STEP_TOLERANCE", 8, raising=False)
    QMessageBox.reset()

    widget = pose_control.PoseControlWidget()
    widget.motor_controller = SettlingMotorController(yaw_steps=2148, pitch_steps=1998)
    widget.spin_home_yaw.setValue(2100)
    widget.spin_home_pitch.setValue(1980)

    moved = widget.move_to_tracking_start_pose()
    drain_homing(widget)

    assert moved is True
    assert QMessageBox.warnings == []
    assert abs(widget.motor_controller.positions[pose_control.config.YAW_MOTOR_ID] - 2100) <= 8
    assert abs(widget.motor_controller.positions[pose_control.config.PITCH_MOTOR_ID] - 1980) <= 8


def test_move_to_tracking_start_pose_succeeds_after_coarse_tolerance_settles(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    monkeypatch.setattr(pose_control.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(pose_control.config, "CENTERING_STEP_TOLERANCE", 8, raising=False)
    monkeypatch.setattr(pose_control.config, "CENTERING_FINAL_STEP_TOLERANCE", 2, raising=False)
    monkeypatch.setattr(pose_control.config, "CENTERING_SETTLE_TICKS", 2, raising=False)
    monkeypatch.setattr(pose_control.config, "CENTERING_TIMEOUT_SEC", 0.3, raising=False)
    QMessageBox.reset()

    ticks = {"value": 0.0}

    def fake_monotonic():
        ticks["value"] += 0.1
        return ticks["value"]

    monkeypatch.setattr(pose_control.time, "monotonic", fake_monotonic)

    widget = pose_control.PoseControlWidget()
    widget.motor_controller = SettlingMotorController(yaw_steps=2148, pitch_steps=1998, yaw_offset=-4, pitch_offset=3)
    widget.spin_home_yaw.setValue(2100)
    widget.spin_home_pitch.setValue(1980)

    moved = widget.move_to_tracking_start_pose()
    drain_homing(widget)

    assert moved is True
    assert widget._homing_active is False
    assert QMessageBox.warnings == []
    assert widget.motor_initialized is True


def test_move_to_tracking_start_pose_surfaces_actual_homing_failure_reason(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    QMessageBox.reset()

    widget = pose_control.PoseControlWidget()

    def fake_start_homing_to_tracking_start(on_success, on_failure):
        on_failure("电机未在时限内完成回中稳定。")
        return False

    widget._start_homing_to_tracking_start = fake_start_homing_to_tracking_start

    moved = widget.move_to_tracking_start_pose()

    assert moved is False
    assert "电机未在时限内完成回中稳定" in QMessageBox.warnings[-1][1]


def test_start_tracking_sequence_surfaces_actual_homing_failure_reason(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    QMessageBox.reset()

    widget = pose_control.PoseControlWidget()
    widget.retargeter = FakeRetargeter()
    widget.motor_controller = FakeMotorController()
    widget.avp_client = FakeAVPClient(np.eye(4), (0.0, 0.0, 0.0))
    widget.set_streaming_ready(True)

    def fake_start_homing_to_tracking_start(on_success, on_failure):
        on_failure("偏航轴未在时限内进入跟踪初始位。")
        return False

    widget._start_homing_to_tracking_start = fake_start_homing_to_tracking_start

    started = widget.start_tracking_sequence()

    assert started is False
    assert "偏航轴未在时限内进入跟踪初始位" in QMessageBox.warnings[-1][1]


def test_start_tracking_sequence_does_not_block_with_sleep_during_homing(monkeypatch):
    pose_control = load_pose_control(monkeypatch)
    monkeypatch.setattr(
        pose_control.time,
        "sleep",
        lambda _seconds: (_ for _ in ()).throw(AssertionError("blocking sleep should not be used during homing")),
    )
    monkeypatch.setattr(pose_control.config, "CENTERING_STEP_TOLERANCE", 8, raising=False)

    widget = pose_control.PoseControlWidget()
    widget.retargeter = FakeRetargeter()
    widget.motor_controller = FakeMotorController(yaw_steps=2148, pitch_steps=1998)
    widget.avp_client = FakeAVPClient(np.eye(4), (0.03, -0.04, 0.0))
    widget.set_streaming_ready(True)
    widget.spin_home_yaw.setValue(pose_control.config.ZERO_POS)
    widget.spin_home_pitch.setValue(pose_control.config.ZERO_POS)

    started = widget.start_tracking_sequence()
    drain_homing(widget)

    assert started is True
    assert widget.is_tracking is True
