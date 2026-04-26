import os
import sys


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

from src.core import app


class FakeStdin:
    def __init__(self, chars):
        self._chars = list(chars)

    def read(self, size):
        if not self._chars:
            return ""
        return self._chars.pop(0)

    def readline(self):
        if not self._chars:
            return ""

        line = []
        while self._chars:
            char = self._chars.pop(0)
            line.append(char)
            if char == "\n":
                break
        return "".join(line)

    def has_data(self):
        return bool(self._chars)


class FakePipeline:
    def __init__(self):
        self.init_requested = 0
        self.resync_requested = 0
        self.reset_requested = 0
        self.confirm_calls = 0

    def request_initialize(self):
        self.init_requested += 1

    def request_resync(self):
        self.resync_requested += 1

    def trigger_recalibration(self):
        self.resync_requested += 1

    def reset_calibration(self):
        self.reset_requested += 1

    def confirm_calibration(self, sample, robot_pose):
        self.confirm_calls += 1
        return object()


def test_trailing_newline_after_initialize_does_not_stop(monkeypatch):
    fake_stdin = FakeStdin("i\n")
    pipeline = FakePipeline()

    monkeypatch.setattr(app.sys, "stdin", fake_stdin)
    monkeypatch.setattr(
        app.select,
        "select",
        lambda reads, _writes, _errors, _timeout: ([fake_stdin], [], []) if fake_stdin.has_data() else ([], [], []),
    )

    action, override = app.handle_user_input(
        controller=None,
        pipeline=pipeline,
        motor_adapter=None,
        sample=None,
        robot_pose=(0.0, 0.0),
    )
    assert action is None
    assert override is None


def test_calibrate_key_requests_resync_without_override(monkeypatch):
    fake_stdin = FakeStdin("c\n")
    pipeline = FakePipeline()

    monkeypatch.setattr(app.sys, "stdin", fake_stdin)
    monkeypatch.setattr(
        app.select,
        "select",
        lambda reads, _writes, _errors, _timeout: ([fake_stdin], [], []) if fake_stdin.has_data() else ([], [], []),
    )

    action, override = app.handle_user_input(
        controller=None,
        pipeline=pipeline,
        motor_adapter=None,
        sample=None,
        robot_pose=(0.0, 0.0),
    )

    assert action is None
    assert override is None
    assert pipeline.resync_requested == 1
    assert pipeline.confirm_calls == 0


def test_recalibration_key_reuses_resync_path(monkeypatch):
    fake_stdin = FakeStdin("k\n")
    pipeline = FakePipeline()

    monkeypatch.setattr(app.sys, "stdin", fake_stdin)
    monkeypatch.setattr(
        app.select,
        "select",
        lambda reads, _writes, _errors, _timeout: ([fake_stdin], [], []) if fake_stdin.has_data() else ([], [], []),
    )

    action, override = app.handle_user_input(
        controller=None,
        pipeline=pipeline,
        motor_adapter=None,
        sample=None,
        robot_pose=(0.0, 0.0),
    )

    assert action is None
    assert override is None
    assert pipeline.resync_requested == 1


def test_reset_key_returns_pipeline_to_centering(monkeypatch):
    fake_stdin = FakeStdin("r\n")
    pipeline = FakePipeline()

    monkeypatch.setattr(app.sys, "stdin", fake_stdin)
    monkeypatch.setattr(
        app.select,
        "select",
        lambda reads, _writes, _errors, _timeout: ([fake_stdin], [], []) if fake_stdin.has_data() else ([], [], []),
    )

    action, override = app.handle_user_input(
        controller=None,
        pipeline=pipeline,
        motor_adapter=None,
        sample=None,
        robot_pose=(0.0, 0.0),
    )

    assert action is None
    assert override is None
    assert pipeline.reset_requested == 1
