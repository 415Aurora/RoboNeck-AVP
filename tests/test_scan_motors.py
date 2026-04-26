import importlib
import os
import sys
import types


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)


def load_scan_module(monkeypatch):
    fake_dxl = types.SimpleNamespace(
        COMM_SUCCESS=0,
        PortHandler=lambda *_args, **_kwargs: None,
        PacketHandler=lambda *_args, **_kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "dynamixel_sdk", fake_dxl)
    sys.modules.pop("tests.scan_motors", None)
    return importlib.import_module("tests.scan_motors")


def test_format_probe_report_includes_failed_stage_and_register(monkeypatch):
    scan_motors = load_scan_module(monkeypatch)

    report = scan_motors.format_probe_report(
        {
            "motor_id": 2,
            "ping_ok": True,
            "model_number": 1234,
            "present_position": 2048,
            "failed_stage": "present_velocity",
            "sdk_error": "COMM_RX_TIMEOUT",
            "status_reads": {
                "present_position": {
                    "address": 132,
                    "bytes": 4,
                    "ok": True,
                    "value": 2048,
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
    )

    assert "failed_stage=present_velocity" in report
    assert "sdk_error=COMM_RX_TIMEOUT" in report
    assert "present_velocity@128/4B=ERROR(COMM_RX_TIMEOUT)" in report
