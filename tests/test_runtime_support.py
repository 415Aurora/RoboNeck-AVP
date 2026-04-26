import importlib
import os
import sys


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)


def test_default_calibration_path_is_project_relative():
    from src.core.paths import get_calibration_path

    assert get_calibration_path() == os.path.join(root_dir, "config", "neck_calibration.json")


def test_calibration_path_can_be_overridden(monkeypatch):
    from src.core.paths import get_calibration_path

    monkeypatch.setenv("ROBO_NECK_CALIBRATION_PATH", "/tmp/custom-neck-calibration.json")

    assert get_calibration_path() == "/tmp/custom-neck-calibration.json"


def test_runtime_preflight_reports_blocking_dependencies_when_not_mocking():
    from src.core.preflight import gather_runtime_checks

    checks = gather_runtime_checks(
        mock_avp=False,
        mock_motors=False,
        enable_video=True,
        use_zed_sdk=True,
        dynamixel_port="/dev/ttyUSB0",
        dependency_status={
            "avp_stream": False,
            "dynamixel_sdk": False,
            "cv2": False,
            "pyzed.sl": False,
        },
        path_exists=lambda _path: False,
    )

    blocking = {check.name: check for check in checks if check.required and not check.ok}

    assert blocking["avp_stream"].message == "Install avp_stream before running with a real Vision Pro."
    assert blocking["dynamixel_sdk"].message == "Install dynamixel_sdk before running with real motors."
    assert blocking["cv2"].message == "Install OpenCV before enabling video streaming."
    assert blocking["pyzed.sl"].message == "Install the ZED SDK Python bindings or disable USE_ZED_SDK."
    assert blocking["dynamixel_port"].message == "Configured Dynamixel port was not found on this machine."


def test_runtime_preflight_allows_mock_modes_without_optional_dependencies():
    from src.core.preflight import gather_runtime_checks

    checks = gather_runtime_checks(
        mock_avp=True,
        mock_motors=True,
        enable_video=False,
        use_zed_sdk=False,
        dynamixel_port="/dev/ttyUSB0",
        dependency_status={
            "avp_stream": False,
            "dynamixel_sdk": False,
            "cv2": False,
            "pyzed.sl": False,
        },
        path_exists=lambda _path: False,
    )

    required_failures = [check for check in checks if check.required and not check.ok]
    assert required_failures == []


def test_runtime_preflight_preserves_dependency_import_error_details():
    from src.core.preflight import gather_runtime_checks

    checks = gather_runtime_checks(
        mock_avp=False,
        mock_motors=True,
        enable_video=False,
        use_zed_sdk=False,
        dynamixel_port="",
        dependency_status={
            "avp_stream": (False, "No module named 'grpc'"),
        },
        path_exists=lambda _path: True,
    )

    avp_stream_check = next(check for check in checks if check.name == "avp_stream")

    assert avp_stream_check.ok is False
    assert "grpc" in avp_stream_check.message


def test_camera_module_imports_without_opencv():
    camera_module = importlib.import_module("src.hardware.camera")

    assert camera_module.cv2 is None

    camera = camera_module.CameraInterface(camera_id=0, resolution="1280x720", fps=30)

    assert camera.is_opened is False
