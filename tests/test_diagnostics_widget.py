import importlib
import os
import sys
import types


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)


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


class QVBoxLayout(Layout):
    pass


class QLabel(QWidget):
    def __init__(self, text=""):
        super().__init__()
        self._text = text

    def setText(self, text):
        self._text = text

    def text(self):
        return self._text

    def setWordWrap(self, _value):
        return None


class QGroupBox(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self._title = title


class QTextBrowser(QWidget):
    def __init__(self):
        super().__init__()
        self.lines = []

    def append(self, text):
        self.lines.append(text)


def load_diagnostics(monkeypatch):
    pyqt6 = types.ModuleType("PyQt6")
    qtwidgets = types.ModuleType("PyQt6.QtWidgets")

    qtwidgets.QWidget = QWidget
    qtwidgets.QGroupBox = QGroupBox
    qtwidgets.QLabel = QLabel
    qtwidgets.QTextBrowser = QTextBrowser
    qtwidgets.QVBoxLayout = QVBoxLayout

    monkeypatch.setitem(sys.modules, "PyQt6", pyqt6)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", qtwidgets)
    sys.modules.pop("src.gui.diagnostics", None)
    return importlib.import_module("src.gui.diagnostics")


def test_diagnostics_widget_shows_paused_tracking_in_summary(monkeypatch):
    diagnostics = load_diagnostics(monkeypatch)
    from src.gui.ui_state import SystemSnapshot

    widget = diagnostics.DiagnosticsWidget()
    widget.update_system_snapshot(
        SystemSnapshot(
            avp_connected=True,
            camera_connected=True,
            motor_connected=True,
            motor_ready=True,
            motor_reason="",
            streaming=True,
            tracking=True,
            tracking_paused=True,
            motor_initialized=True,
            pose_initialized=True,
            pose_sample_valid=False,
            pose_sample_reason="stale_sample",
            pose_sample_fresh=False,
            last_warning="[TRACK] PAUSED reason=stale_sample",
        )
    )

    assert "跟踪=已暂停" in widget.label_summary.text()
    assert "stale_sample" in widget.label_summary.text()
