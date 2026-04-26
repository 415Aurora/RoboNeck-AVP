from config import config
from src.hardware.camera import (
    CameraInterface,
    _default_device_info,
    _default_health_status,
    _default_sensor_snapshot,
    _default_streaming_status,
)


class CameraController:
    """
    Independent lifecycle manager for the ZED camera.
    """

    def __init__(self):
        self.camera = None
        self.resolution = getattr(config, "STREAM_RESOLUTION", "1280x720")
        self.fps = config.STREAM_FPS

    @property
    def is_connected(self):
        return bool(self.camera and getattr(self.camera, "is_opened", False))

    def _camera_matches(self, resolution, fps):
        if not self.is_connected:
            return False

        try:
            width, height = map(int, resolution.split("x"))
        except Exception:
            return False

        return (
            getattr(self.camera, "width", None) == width
            and getattr(self.camera, "height", None) == height
            and getattr(self.camera, "fps", None) == fps
        )

    def open_camera(self, resolution=None, fps=None):
        self.resolution = resolution or self.resolution
        self.fps = fps or self.fps

        if self._camera_matches(self.resolution, self.fps):
            return self.camera

        if self.camera:
            self.close_camera()

        camera = CameraInterface(resolution=self.resolution, fps=self.fps)
        if not camera.is_opened:
            self.camera = None
            return None

        self.camera = camera
        return self.camera

    def close_camera(self):
        if self.camera:
            self.camera.close()
            self.camera = None

    def read(self):
        if self.camera:
            return self.camera.read()
        return False, None

    def get_imu_data(self):
        if self.camera:
            return self.camera.get_imu_data()
        return None

    def get_device_info(self):
        if self.camera:
            return self.camera.get_device_info()
        return _default_device_info(
            backend="unavailable",
            connected=False,
            sdk_available=False,
            model="Camera unavailable",
            serial_number="N/A",
            firmware_version="N/A",
            sensors_firmware_version="N/A",
            resolution=self.resolution,
            fps=self.fps,
            capabilities={
                "supports_manual_focus": False,
                "supports_auto_focus": False,
                "supports_depth_controls": False,
                "supports_sensor_snapshot": False,
                "supports_health_status": False,
                "supports_streaming": False,
            },
        )

    def get_sensor_snapshot(self):
        if self.camera:
            return self.camera.get_sensor_snapshot()
        return _default_sensor_snapshot("unavailable", False)

    def get_health_status(self):
        if self.camera:
            return self.camera.get_health_status()
        return _default_health_status("unavailable", False)

    def get_streaming_status(self):
        if self.camera:
            return self.camera.get_streaming_status()
        return _default_streaming_status("unavailable", False)

    def set_exposure(self, value):
        return bool(self.camera and self.camera.set_exposure(value))

    def set_whitebalance(self, value):
        return bool(self.camera and self.camera.set_whitebalance(value))

    def set_gain(self, value):
        return bool(self.camera and self.camera.set_gain(value))

    def set_auto_exposure(self, enabled):
        return bool(self.camera and self.camera.set_auto_exposure(enabled))

    def set_auto_whitebalance(self, enabled):
        return bool(self.camera and self.camera.set_auto_whitebalance(enabled))

    def set_confidence_threshold(self, value):
        return bool(self.camera and self.camera.set_confidence_threshold(value))

    def set_disparity_range(self, value):
        return bool(self.camera and self.camera.set_disparity_range(value))

    def set_view_mode(self, mode):
        return bool(self.camera and self.camera.set_view_mode(mode))

    def set_focus(self, value):
        return bool(self.camera and self.camera.set_focus(value))

    def set_auto_focus(self, enabled):
        if not self.camera:
            return False
        return self.camera.set_auto_focus(enabled)

    def enable_streaming(self, codec="H264", bitrate=8000, port=30000):
        return bool(self.camera and self.camera.enable_streaming(codec=codec, bitrate=bitrate, port=port))

    def disable_streaming(self):
        return bool(self.camera and self.camera.disable_streaming())
