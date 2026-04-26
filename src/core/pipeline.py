from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from src.core.controller import HeadPoseSample
from src.utils.orientation import extract_avp_head_angles


class PipelineState(Enum):
    READY = "ready"
    CENTERING = "centering"
    SYNCING = "syncing"
    CALIBRATING = "calibrating"
    WAIT_FOR_AVP = "wait_for_avp"
    TRACKING = "tracking"
    HOLD = "hold"
    FAULT = "fault"


@dataclass
class PipelineResult:
    state: PipelineState
    neck_target: Optional[Tuple[float, float]]
    reason: str = ""
    calibrated: bool = False


class HeadPosePipeline:
    def __init__(self, retargeter, avp_timeout_sec, center_tolerance_rad=0.05, auto_initialize=True):
        self.retargeter = retargeter
        self.avp_timeout_sec = avp_timeout_sec
        self.center_tolerance_rad = center_tolerance_rad
        self.last_valid_timestamp = None
        self.aligned = False
        self.needs_realign = False
        self.state = PipelineState.CENTERING if auto_initialize else PipelineState.READY

    def process(self, sample, robot_pose, now):
        if self.state is PipelineState.READY:
            return PipelineResult(state=PipelineState.READY, neck_target=None, reason="waiting_for_init", calibrated=False)

        if self.state is PipelineState.CENTERING:
            if not self._is_centered(robot_pose):
                return PipelineResult(state=PipelineState.CENTERING, neck_target=(0.0, 0.0), reason="centering", calibrated=False)
            self.state = PipelineState.SYNCING

        if self.state in {PipelineState.SYNCING, PipelineState.CALIBRATING}:
            return self._sync_or_wait(sample, robot_pose, now)

        if sample is None:
            return self._handle_missing(now)

        sample_timestamp = sample.timestamp if sample.timestamp is not None else now
        if now - sample_timestamp > self.avp_timeout_sec:
            self.last_valid_timestamp = sample_timestamp
            self.needs_realign = True
            return PipelineResult(state=PipelineState.HOLD, neck_target=None, reason="avp_timeout")

        self.last_valid_timestamp = sample_timestamp

        try:
            if not self.aligned or self.needs_realign:
                self.state = PipelineState.SYNCING
                return self._sync_or_wait(sample, robot_pose, now)

            yaw_target, pitch_target = self.retargeter.compute_neck_target(
                sample.head_pose_matrix,
                base_imu_rpy=sample.base_imu_rpy,
            )
            self.state = PipelineState.TRACKING
            return PipelineResult(
                state=PipelineState.TRACKING,
                neck_target=(yaw_target, pitch_target),
                reason="tracking",
                calibrated=True,
            )
        except Exception as exc:
            return PipelineResult(state=PipelineState.FAULT, neck_target=None, reason=str(exc), calibrated=self.aligned)

    def trigger_recalibration(self):
        self.request_resync()

    def reset_calibration(self):
        self.aligned = False
        self.needs_realign = False
        self.state = PipelineState.CENTERING
        self.retargeter.reset_calibration()

    def request_initialize(self):
        self.request_resync()

    def request_resync(self):
        self.aligned = False
        self.needs_realign = False
        self.state = PipelineState.CENTERING
        if hasattr(self.retargeter, "request_resync"):
            self.retargeter.request_resync()

    def confirm_calibration(self, sample, robot_pose):
        if self.state not in {PipelineState.CALIBRATING, PipelineState.SYNCING}:
            return PipelineResult(state=self.state, neck_target=None, reason="not_calibrating", calibrated=self.aligned)
        return self._sync_or_wait(sample, robot_pose, sample.timestamp if sample is not None else None)

    def _handle_missing(self, now):
        if self.last_valid_timestamp is None:
            self.state = PipelineState.WAIT_FOR_AVP
            return PipelineResult(state=PipelineState.WAIT_FOR_AVP, neck_target=None, reason="waiting_for_sample")

        if now - self.last_valid_timestamp > self.avp_timeout_sec:
            self.needs_realign = True
            self.state = PipelineState.HOLD
            return PipelineResult(state=PipelineState.HOLD, neck_target=None, reason="avp_timeout", calibrated=self.aligned)

        self.state = PipelineState.HOLD
        return PipelineResult(state=PipelineState.HOLD, neck_target=None, reason="sample_missing", calibrated=self.aligned)

    def _sync_or_wait(self, sample, robot_pose, now):
        if sample is None:
            self.state = PipelineState.SYNCING
            return PipelineResult(state=PipelineState.SYNCING, neck_target=None, reason="waiting_for_sample", calibrated=False)

        sample_timestamp = sample.timestamp if sample.timestamp is not None else now
        if now is not None and now - sample_timestamp > self.avp_timeout_sec:
            self.state = PipelineState.SYNCING
            return PipelineResult(state=PipelineState.SYNCING, neck_target=None, reason="waiting_for_fresh_sample", calibrated=False)

        self._sync(sample, robot_pose)
        self.last_valid_timestamp = sample_timestamp
        self.aligned = True
        reason = "realigned" if self.needs_realign else "auto_synced"
        self.needs_realign = False
        self.state = PipelineState.TRACKING
        return PipelineResult(state=PipelineState.TRACKING, neck_target=robot_pose, reason=reason, calibrated=True)

    def _sync(self, sample, robot_pose):
        if hasattr(self.retargeter, "sync_to_robot_pose"):
            self.retargeter.sync_to_robot_pose(
                sample.head_pose_matrix,
                robot_pose=robot_pose,
                base_imu_rpy=sample.base_imu_rpy,
            )
            return

        rotation_matrix = sample.head_pose_matrix[:3, :3] if sample.head_pose_matrix.shape == (4, 4) else sample.head_pose_matrix
        avp_yaw, avp_pitch = extract_avp_head_angles(rotation_matrix)
        self.retargeter.sync_offsets(avp_yaw, avp_pitch, robot_pose[0], robot_pose[1])

    def _is_centered(self, robot_pose):
        return abs(robot_pose[0]) <= self.center_tolerance_rad and abs(robot_pose[1]) <= self.center_tolerance_rad
