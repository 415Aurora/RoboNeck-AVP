import os
import sys


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

from src.hardware.camera import CameraInterface


class DummyZedWrapper:
    def get_device_info(self):
        return {
            "backend": "zed_sdk",
            "connected": True,
            "sdk_available": True,
            "model": "ZED-M",
            "serial_number": 12345,
            "firmware_version": 100,
            "sensors_firmware_version": 200,
            "resolution": "1280x720",
            "fps": 30,
            "capabilities": {
                "supports_manual_focus": True,
                "supports_auto_focus": False,
                "supports_depth_controls": True,
                "supports_sensor_snapshot": True,
                "supports_health_status": True,
                "supports_streaming": True,
            },
        }

    def get_sensor_snapshot(self):
        return {
            "backend": "zed_sdk",
            "supported": True,
            "imu": {"available": True, "fresh": True, "rpy_rad": [0.1, -0.2, 0.0]},
            "magnetometer": {"available": True, "fresh": True, "field_ut": [1.0, 2.0, 3.0]},
            "barometer": {"available": True, "fresh": False, "pressure_hpa": 1001.2},
        }

    def get_health_status(self):
        return {
            "backend": "zed_sdk",
            "supported": True,
            "enabled": True,
            "low_image_quality": False,
            "low_lighting": False,
            "low_depth_reliability": False,
            "low_motion_sensors_reliability": False,
            "last_grab_status": "SUCCESS",
        }

    def get_streaming_status(self):
        return {
            "backend": "zed_sdk",
            "supported": True,
            "enabled": True,
            "codec": "H265",
            "bitrate_kbps": 10000,
            "port": 30000,
            "last_error": "",
        }


def make_camera(zed=None):
    camera = CameraInterface.__new__(CameraInterface)
    camera.camera_id = 0
    camera.width = 1280
    camera.height = 720
    camera.fps = 30
    camera.is_opened = zed is not None
    camera.zed = zed
    camera.cap = None
    return camera


def test_camera_interface_fallback_device_info_has_stable_shape():
    camera = make_camera()

    info = camera.get_device_info()

    assert info["backend"] == "unavailable"
    assert info["connected"] is False
    assert info["resolution"] == "1280x720"
    assert info["capabilities"]["supports_streaming"] is False


def test_camera_interface_fallback_sensor_and_health_status_are_explicit():
    camera = make_camera()

    sensor_snapshot = camera.get_sensor_snapshot()
    health_status = camera.get_health_status()
    stream_status = camera.get_streaming_status()

    assert sensor_snapshot["supported"] is False
    assert sensor_snapshot["imu"]["available"] is False
    assert health_status["supported"] is False
    assert stream_status["supported"] is False
    assert stream_status["enabled"] is False


def test_camera_interface_uses_zed_wrapper_status_interfaces_when_available():
    camera = make_camera(DummyZedWrapper())

    assert camera.get_device_info()["backend"] == "zed_sdk"
    assert camera.get_sensor_snapshot()["imu"]["available"] is True
    assert camera.get_health_status()["supported"] is True
    assert camera.get_streaming_status()["codec"] == "H265"
