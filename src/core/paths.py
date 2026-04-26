import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CALIBRATION_PATH = PROJECT_ROOT / "config" / "neck_calibration.json"
DEFAULT_TRACKING_START_PATH = PROJECT_ROOT / "config" / "tracking_start_pose.json"
DEFAULT_MOTOR_LIMITS_PATH = PROJECT_ROOT / "config" / "motor_limits.json"
DEFAULT_AVP_CONNECTION_PATH = PROJECT_ROOT / "config" / "avp_connection.json"
CALIBRATION_PATH_ENV = "ROBO_NECK_CALIBRATION_PATH"
TRACKING_START_PATH_ENV = "ROBO_NECK_TRACKING_START_PATH"
MOTOR_LIMITS_PATH_ENV = "ROBO_NECK_MOTOR_LIMITS_PATH"
AVP_CONNECTION_PATH_ENV = "ROBO_NECK_AVP_CONNECTION_PATH"


def get_project_root():
    return str(PROJECT_ROOT)


def get_calibration_path():
    return os.getenv(CALIBRATION_PATH_ENV, str(DEFAULT_CALIBRATION_PATH))


def get_tracking_start_path():
    return os.getenv(TRACKING_START_PATH_ENV, str(DEFAULT_TRACKING_START_PATH))


def get_motor_limits_path():
    return os.getenv(MOTOR_LIMITS_PATH_ENV, str(DEFAULT_MOTOR_LIMITS_PATH))


def get_avp_connection_path():
    return os.getenv(AVP_CONNECTION_PATH_ENV, str(DEFAULT_AVP_CONNECTION_PATH))
