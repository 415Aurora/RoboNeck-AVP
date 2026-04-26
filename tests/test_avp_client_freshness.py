import os
import sys
import time
import threading

import numpy as np


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

from src.core.client import AVPClient
import src.core.client as client_module


class FakeStreamer:
    def __init__(self, payloads):
        self.payloads = list(payloads)

    def get_latest(self):
        if not self.payloads:
            return None
        return self.payloads.pop(0)


def make_pose(yaw_rad=0.0):
    pose = np.eye(4)
    cy = np.cos(yaw_rad)
    sy = np.sin(yaw_rad)
    pose[0, 0] = cy
    pose[0, 2] = sy
    pose[2, 0] = -sy
    pose[2, 2] = cy
    return pose


def make_client(payloads):
    client = AVPClient.__new__(AVPClient)
    client.streamer = FakeStreamer(payloads)
    client._streamer_lock = threading.Lock()
    client._streamer_thread = None
    client._streamer_error = None
    client.camera = None
    client.running = False
    client.using_dummy_video = False
    client._last_sample_timestamp = None
    client._last_head_matrix = None
    client._last_pose_status = {
        "valid": False,
        "reason": "uninitialized",
        "fresh": False,
        "last_sample_timestamp": None,
        "source_timestamp": None,
        "last_matrix_shape": None,
    }
    return client


def test_client_uses_local_receive_time_when_upstream_timestamp_is_missing():
    client = make_client([
        {"head": make_pose(0.1)},
    ])

    sample = client.get_latest_head_pose_sample(now=12.5)

    assert sample.timestamp == 12.5
    assert sample.fresh is True
    assert sample.source_timestamp is None
    assert sample.raw_payload["fresh"] is True
    assert sample.raw_payload["source_timestamp"] is None


def test_client_starts_idle_until_operator_requests_manual_connection():
    client = AVPClient("172.20.10.4")

    assert client.streamer is None
    assert client.get_connection_status()["state"] == "idle"
    assert client.get_pose_status()["reason"] == "idle"


def test_client_manual_connect_does_not_block_while_streamer_connects_in_background():
    original_streamer = client_module.VisionProStreamer

    class SlowStreamer:
        def __init__(self, ip, record=True):
            time.sleep(0.5)
            self.ip = ip

        def get_latest(self):
            return None

        def cleanup(self):
            return None

    client_module.VisionProStreamer = SlowStreamer
    try:
        client = AVPClient("172.20.10.4")
        started = time.time()
        client.connect(auto_reconnect=False)
        elapsed = time.time() - started

        assert elapsed < 0.2
        assert client.streamer is None
        assert client._streamer_thread is not None
        assert client.get_connection_status()["state"] == "connecting"
    finally:
        client.disconnect()
        client_module.VisionProStreamer = original_streamer


def test_client_auto_reconnect_eventually_recovers_after_initial_connect_failure(monkeypatch):
    original_streamer = client_module.VisionProStreamer
    attempts = []

    class FlakyStreamer:
        def __init__(self, ip, record=True):
            attempts.append(ip)
            if len(attempts) == 1:
                raise RuntimeError("connection refused")
            self.ip = ip

        def get_latest(self):
            return None

        def cleanup(self):
            return None

    monkeypatch.setattr(client_module, "AVP_RECONNECT_RETRY_SEC", 0.01, raising=False)
    client_module.VisionProStreamer = FlakyStreamer
    try:
        client = AVPClient("172.20.10.4")
        client.connect(auto_reconnect=True)

        deadline = time.time() + 0.3
        while time.time() < deadline and client.streamer is None:
            time.sleep(0.01)

        assert len(attempts) >= 2
        assert client.streamer is not None
        assert client.get_connection_status()["state"] == "connected_waiting_first_sample"
    finally:
        client.disconnect()
        client_module.VisionProStreamer = original_streamer


def test_client_disconnect_stops_auto_reconnect_attempts(monkeypatch):
    original_streamer = client_module.VisionProStreamer
    attempts = []

    class AlwaysFailStreamer:
        def __init__(self, ip, record=True):
            attempts.append(ip)
            raise RuntimeError("connection refused")

    monkeypatch.setattr(client_module, "AVP_RECONNECT_RETRY_SEC", 0.01, raising=False)
    client_module.VisionProStreamer = AlwaysFailStreamer
    try:
        client = AVPClient("172.20.10.4")
        client.connect(auto_reconnect=True)

        deadline = time.time() + 0.2
        while time.time() < deadline and len(attempts) < 2:
            time.sleep(0.01)

        client.disconnect()
        attempts_after_disconnect = len(attempts)
        time.sleep(0.05)

        assert attempts_after_disconnect >= 1
        assert len(attempts) == attempts_after_disconnect
        assert client.get_connection_status()["state"] == "disconnected"
    finally:
        client_module.VisionProStreamer = original_streamer


def test_client_reports_streamer_initializing_while_background_connect_runs():
    client = AVPClient.__new__(AVPClient)
    client.streamer = None
    client._streamer_lock = threading.Lock()
    client._streamer_thread = threading.Thread(target=lambda: None)
    client._streamer_error = None
    client._connect_requested = True
    client._auto_reconnect = False
    client.camera = None
    client.running = False
    client.using_dummy_video = False
    client._connection_status = {
        "state": "connecting",
        "ip": "172.20.10.4",
        "auto_reconnect": False,
        "last_error": None,
        "state_since_monotonic": time.monotonic(),
        "last_sample_timestamp": None,
        "has_ever_received_pose": False,
    }
    client._last_sample_timestamp = None
    client._last_head_matrix = None
    client._last_pose_status = {
        "valid": False,
        "reason": "streamer_not_ready",
        "fresh": False,
        "last_sample_timestamp": None,
        "source_timestamp": None,
        "last_matrix_shape": None,
    }

    sample = client.get_latest_head_pose_sample(now=12.5)

    assert sample is None
    assert client.get_pose_status()["reason"] == "streamer_initializing"


def test_client_get_pose_status_reflects_background_initializing_state_without_sampling():
    client = AVPClient.__new__(AVPClient)
    client.streamer = None
    client._streamer_lock = threading.Lock()
    client._streamer_thread = threading.Thread(target=lambda: None)
    client._streamer_error = None
    client._connect_requested = True
    client._auto_reconnect = False
    client._streamer_import_error = ""
    client.camera = None
    client.running = False
    client.using_dummy_video = False
    client._connection_status = {
        "state": "connecting",
        "ip": "172.20.10.4",
        "auto_reconnect": False,
        "last_error": None,
        "state_since_monotonic": time.monotonic(),
        "last_sample_timestamp": None,
        "has_ever_received_pose": False,
    }
    client._last_sample_timestamp = None
    client._last_head_matrix = None
    client._last_pose_status = {
        "valid": False,
        "reason": "streamer_not_ready",
        "fresh": False,
        "last_sample_timestamp": None,
        "source_timestamp": None,
        "last_matrix_shape": None,
        "error": None,
    }

    status = client.get_pose_status()

    assert status["reason"] == "streamer_initializing"
    assert status["state_age_sec"] >= 0.0


def test_client_get_pose_status_reports_initializing_state_age(monkeypatch):
    client = AVPClient.__new__(AVPClient)
    client.streamer = None
    client._streamer_lock = threading.Lock()
    client._streamer_thread = threading.Thread(target=lambda: None)
    client._streamer_error = None
    client._connect_requested = True
    client._auto_reconnect = False
    client._streamer_import_error = ""
    client.camera = None
    client.running = False
    client.using_dummy_video = False
    client._connection_status = {
        "state": "connecting",
        "ip": "172.20.10.4",
        "auto_reconnect": False,
        "last_error": None,
        "state_since_monotonic": 5.0,
        "last_sample_timestamp": None,
        "has_ever_received_pose": False,
    }
    client._last_sample_timestamp = None
    client._last_head_matrix = None
    client._last_pose_status = {
        "valid": False,
        "reason": "streamer_initializing",
        "fresh": False,
        "last_sample_timestamp": None,
        "source_timestamp": None,
        "last_matrix_shape": None,
        "error": None,
        "state_since_monotonic": 5.0,
    }
    monkeypatch.setattr(client_module.time, "monotonic", lambda: 9.8)

    status = client.get_pose_status()

    assert status["reason"] == "streamer_initializing"
    assert status["state_age_sec"] == 4.8


def test_client_reports_streamer_init_failed_when_background_connect_raises():
    client = AVPClient.__new__(AVPClient)
    client.streamer = None
    client._streamer_lock = threading.Lock()
    client._streamer_thread = None
    client._streamer_error = RuntimeError("connection refused")
    client._connect_requested = False
    client._auto_reconnect = False
    client.camera = None
    client.running = False
    client.using_dummy_video = False
    client._connection_status = {
        "state": "connect_failed",
        "ip": "172.20.10.4",
        "auto_reconnect": False,
        "last_error": "connection refused",
        "state_since_monotonic": time.monotonic(),
        "last_sample_timestamp": None,
        "has_ever_received_pose": False,
    }
    client._last_sample_timestamp = None
    client._last_head_matrix = None
    client._last_pose_status = {
        "valid": False,
        "reason": "streamer_not_ready",
        "fresh": False,
        "last_sample_timestamp": None,
        "source_timestamp": None,
        "last_matrix_shape": None,
    }

    sample = client.get_latest_head_pose_sample(now=12.5)

    assert sample is None
    status = client.get_pose_status()
    assert status["reason"] == "streamer_init_failed"
    assert status["error"] == "connection refused"


def test_client_get_pose_status_reflects_streamer_connected_but_waiting_first_sample():
    client = make_client([])
    client._streamer_import_error = ""
    client._connection_status = {
        "state": "connected_waiting_first_sample",
        "ip": "172.20.10.4",
        "auto_reconnect": False,
        "last_error": None,
        "state_since_monotonic": time.monotonic(),
        "last_sample_timestamp": None,
        "has_ever_received_pose": False,
    }

    status = client.get_pose_status()

    assert status["reason"] == "stream_established_waiting_first_sample"
    assert status["state_age_sec"] >= 0.0


def test_client_get_pose_status_reports_waiting_first_sample_state_age(monkeypatch):
    client = make_client([])
    client._streamer_import_error = ""
    client._connection_status = {
        "state": "connected_waiting_first_sample",
        "ip": "172.20.10.4",
        "auto_reconnect": False,
        "last_error": None,
        "state_since_monotonic": 2.0,
        "last_sample_timestamp": None,
        "has_ever_received_pose": False,
    }
    client._last_pose_status = {
        "valid": False,
        "reason": "stream_established_waiting_first_sample",
        "fresh": False,
        "last_sample_timestamp": None,
        "source_timestamp": None,
        "last_matrix_shape": None,
        "error": None,
        "state_since_monotonic": 2.0,
    }
    monkeypatch.setattr(client_module.time, "monotonic", lambda: 6.5)

    status = client.get_pose_status()

    assert status["reason"] == "stream_established_waiting_first_sample"
    assert status["state_age_sec"] == 4.5


def test_client_reports_waiting_first_sample_when_streamer_is_connected_but_empty():
    client = make_client([])
    client._connection_status = {
        "state": "connected_waiting_first_sample",
        "ip": "172.20.10.4",
        "auto_reconnect": False,
        "last_error": None,
        "state_since_monotonic": time.monotonic(),
        "last_sample_timestamp": None,
        "has_ever_received_pose": False,
    }

    sample = client.get_latest_head_pose_sample(now=12.5)

    assert sample is None
    assert client.get_pose_status()["reason"] == "stream_established_waiting_first_sample"


def test_client_marks_sample_invalid_when_payload_has_no_head_matrix():
    client = make_client([
        {"timestamp": 10.0},
    ])

    sample = client.get_latest_head_pose_sample(now=12.5)

    assert sample is None
    assert client.get_pose_status()["valid"] is False
    assert client.get_pose_status()["reason"] == "missing_head_field"


def test_client_marks_sample_invalid_when_head_matrix_shape_is_wrong():
    client = make_client([
        {"head": np.eye(3, 4)},
    ])

    sample = client.get_latest_head_pose_sample(now=12.5)

    assert sample is None
    assert client.get_pose_status()["valid"] is False
    assert client.get_pose_status()["reason"] == "invalid_head_shape"
    assert client.get_pose_status()["last_matrix_shape"] == (3, 4)


def test_client_marks_sample_invalid_when_head_matrix_contains_non_finite_values():
    pose = make_pose(0.2)
    pose[0, 0] = np.nan
    client = make_client([
        {"head": pose},
    ])

    sample = client.get_latest_head_pose_sample(now=12.5)

    assert sample is None
    assert client.get_pose_status()["valid"] is False
    assert client.get_pose_status()["reason"] == "invalid_head_values"


def test_get_latest_head_pose_matrix_reuses_last_valid_sample_when_new_payload_is_invalid():
    valid_pose = make_pose(0.35)
    client = make_client([
        {"head": valid_pose, "timestamp": 3.0},
        {"head": np.eye(3, 4), "timestamp": 4.0},
    ])

    sample = client.get_latest_head_pose_sample(now=5.0)
    matrix = client.get_latest_head_pose_matrix()

    assert sample is not None
    assert np.allclose(sample.head_pose_matrix, valid_pose)
    assert np.allclose(matrix, valid_pose)
    assert client.get_pose_status()["valid"] is False
    assert client.get_pose_status()["reason"] == "invalid_head_shape"
