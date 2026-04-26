import numpy as np
from config import config
from src.utils.orientation import extract_avp_head_euler

class EMASmoother:
    """
    Exponential Moving Average smoother for scalar values.
    """
    def __init__(self, alpha=0.5, initial_value=None):
        self.alpha = alpha
        self.value = initial_value

    def update(self, new_value):
        if self.value is None:
            self.value = new_value
        else:
            self.value = self.alpha * new_value + (1 - self.alpha) * self.value
        return self.value

class HeadRetargeter:
    """
    Handles the coordinate transformation and angle extraction from 
    Apple Vision Pro (AVP) head pose to Robot Neck motors (Yaw, Pitch).
    """

    VALID_BASE_IMU_COMPENSATION_MODES = {"off", "pitch_only", "yaw_pitch"}

    def __init__(self, base_imu_compensation_mode=None):
        # Initialize smoothers for Yaw and Pitch
        # Alpha from config: default 0.2 (strong smoothing) -> 1.0 (no smoothing)
        alpha = getattr(config, 'SMOOTHING_ALPHA', 0.2)
        self.yaw_smoother = EMASmoother(alpha=alpha)
        self.pitch_smoother = EMASmoother(alpha=alpha)
        
        # Calibration offsets
        self.yaw_offset = 0.0
        self.pitch_offset = 0.0
        self.calibrated = False
        self._pending_calibration = False
        if base_imu_compensation_mode is None:
            base_imu_compensation_mode = getattr(config, "ZED_IMU_COMPENSATION_MODE", "off")
        self.set_base_imu_compensation_mode(base_imu_compensation_mode)

    def set_base_imu_compensation_mode(self, mode):
        if mode not in self.VALID_BASE_IMU_COMPENSATION_MODES:
            raise ValueError(f"Unsupported base IMU compensation mode: {mode}")
        self.base_imu_compensation_mode = mode

    def _extract_raw_targets(self, head_pose_mat, base_imu_rpy=None):
        if head_pose_mat.shape == (4, 4):
            head_rotation = head_pose_mat[:3, :3]
        else:
            head_rotation = head_pose_mat

        avp_yaw, avp_pitch, _avp_roll = extract_avp_head_euler(head_rotation)
        raw_yaw = -avp_yaw
        raw_pitch = -avp_pitch

        if base_imu_rpy is not None:
            b_yaw, b_pitch, _b_roll = base_imu_rpy
            if self.base_imu_compensation_mode == "yaw_pitch":
                raw_yaw -= b_yaw
            if self.base_imu_compensation_mode in {"pitch_only", "yaw_pitch"}:
                raw_pitch -= b_pitch

        return raw_yaw, raw_pitch

    def _apply_sync(self, raw_yaw, raw_pitch, robot_pose):
        self.yaw_offset = raw_yaw - robot_pose[0]
        self.pitch_offset = raw_pitch - robot_pose[1]
        self.yaw_smoother.value = robot_pose[0]
        self.pitch_smoother.value = robot_pose[1]
        self.calibrated = True
        self._pending_calibration = False
        print(f"[Calibration] Synced to Robot. Offset Yaw: {self.yaw_offset:.3f}")

    def sync_to_robot_pose(self, head_pose_mat, robot_pose, base_imu_rpy=None):
        raw_yaw, raw_pitch = self._extract_raw_targets(head_pose_mat, base_imu_rpy=base_imu_rpy)
        self._apply_sync(raw_yaw, raw_pitch, robot_pose)

    def request_resync(self):
        self.yaw_offset = 0.0
        self.pitch_offset = 0.0
        self.calibrated = False
        self._pending_calibration = False

    def trigger_calibration(self):
        """
        Compatibility wrapper for legacy callers.
        """
        self.request_resync()

    def reset_calibration(self):
        """
        Reset offsets to zero (Absolute AVP Pose).
        """
        self.request_resync()
        print("[Calibration] Reset to Absolute (Offsets Cleared).")

    def sync_offsets(self, avp_yaw, avp_pitch, robot_yaw, robot_pitch):
        """
        Set offsets such that (AVP - Offset) = Robot.
        Offset = AVP - Robot.
        Used to prevent jumping when starting tracking.
        """
        # Note: AVP/Robot yaw/pitch should be in same coordinate frame/direction
        # compute_neck_target does scaling/direction internally, so we might need to be careful.
        # Ideally we act on raw input.
        # But compute_neck_target logic is: Target = -AVP - Offset.
        # We want: Target = Robot.
        # Robot = -AVP - Offset => Offset = -AVP - Robot.
        
        # Check standard mapping in compute_neck_target:
        # raw_yaw = -avp_yaw
        # target_yaw = raw_yaw - self.yaw_offset
        # So: target_yaw = -avp_yaw - self.yaw_offset
        # We want target_yaw = robot_yaw
        # robot_yaw = -avp_yaw - self.yaw_offset
        # self.yaw_offset = -avp_yaw - robot_yaw
        
        raw_yaw = -avp_yaw
        raw_pitch = -avp_pitch
        self._apply_sync(raw_yaw, raw_pitch, (robot_yaw, robot_pitch))

    def compute_neck_target(self, head_pose_mat, base_imu_rpy=None):
        """
        Compute target Yaw and Pitch for the robot neck.

        Args:
            head_pose_mat (np.ndarray): 4x4 Homogeneous matrix or 3x3 Rotation matrix from AVP.
            base_imu_rpy (tuple, optional): (yaw, pitch, roll) in radians from robot base IMU. 
                                            If provided, compensates for base movement.

        Returns:
            tuple: (yaw, pitch) in radians, ensuring ranges are safe.
        """
        raw_yaw, raw_pitch = self._extract_raw_targets(head_pose_mat, base_imu_rpy=base_imu_rpy)

        target_yaw = raw_yaw - self.yaw_offset
        target_pitch = raw_pitch - self.pitch_offset

        smooth_yaw = self.yaw_smoother.update(target_yaw)
        smooth_pitch = self.pitch_smoother.update(target_pitch)

        return smooth_yaw, smooth_pitch
