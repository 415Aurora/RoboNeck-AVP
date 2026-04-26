from dataclasses import dataclass
from typing import Dict, Optional

from src.core.controller import ControlState, ControllerResult


@dataclass
class RuntimeStatus:
    state: ControlState
    tracking_active: bool
    tracking_paused: bool
    calibration_ready: bool
    fault_latched: bool
    reason: str


class ControlRuntime:
    def __init__(
        self,
        controller,
        tracking_start_positions,
        centering_step_tolerance=8,
        io_fault_threshold=3,
        sync_pose_override=(0.0, 0.0),
    ):
        self.controller = controller
        self.tracking_start_positions = {
            int(motor_id): int(position) for motor_id, position in dict(tracking_start_positions).items()
        }
        self.centering_step_tolerance = int(max(0, centering_step_tolerance))
        self.io_fault_threshold = int(max(1, io_fault_threshold))
        self.sync_pose_override = tuple(sync_pose_override) if sync_pose_override is not None else None

        self.mode = ControlState.READY
        self.auto_track_after_sync = False
        self.resync_required = False
        self.fault_latched = False
        self.io_failure_count = 0
        self.last_result = ControllerResult(state=ControlState.READY, commands={}, reason="ready")

    def request_start_tracking(self):
        if self.fault_latched:
            return self.last_result
        self.auto_track_after_sync = True
        self.resync_required = False
        self.mode = ControlState.CENTERING
        return self.last_result

    def request_move_to_start_pose(self):
        if self.fault_latched:
            return self.last_result
        self.auto_track_after_sync = False
        self.resync_required = False
        self.mode = ControlState.CENTERING
        return self.last_result

    def request_resync(self, auto_track=False):
        if self.fault_latched:
            return self.last_result
        self.auto_track_after_sync = bool(auto_track)
        self.resync_required = False
        self.mode = ControlState.CENTERING
        return self.last_result

    def request_stop(self):
        self.auto_track_after_sync = False
        self.mode = ControlState.READY
        return self._hold_current("stopped")

    def reset_fault(self):
        self.fault_latched = False
        self.io_failure_count = 0
        self.resync_required = False
        self.auto_track_after_sync = False
        self.mode = ControlState.READY
        self.controller.robot_synced = False
        return self.last_result

    def update_tracking_start_positions(self, tracking_start_positions):
        self.tracking_start_positions = {
            int(motor_id): int(position) for motor_id, position in dict(tracking_start_positions).items()
        }

    def handle_io_failure(self, reason):
        self.io_failure_count += 1
        self.resync_required = True
        if self.io_failure_count >= self.io_fault_threshold:
            self.fault_latched = True
            self.mode = ControlState.FAULT
            self.last_result = ControllerResult(
                state=ControlState.FAULT,
                commands={},
                reason=str(reason),
                hold_position=self.controller.hold_position(),
            )
            return self.last_result
        return self._hold_current(str(reason))

    def tick(self, sample, motor_positions, now):
        if self.fault_latched:
            self.last_result = ControllerResult(
                state=ControlState.FAULT,
                commands={},
                reason=self.last_result.reason or "fault_latched",
                hold_position=self.controller.hold_position(),
            )
            return self.last_result

        if self.mode is ControlState.CENTERING:
            if not self._is_centered(motor_positions):
                self.io_failure_count = 0
                result = self.controller.update_step_targets(
                    self.tracking_start_positions,
                    motor_positions=motor_positions,
                    reason="centering",
                    state_override=ControlState.CENTERING,
                )
                self.mode = result.state
                self.last_result = result
                return result
            self.mode = ControlState.SYNCING

        if self.mode is ControlState.SYNCING:
            return self._sync(sample, motor_positions, now)

        if self.resync_required:
            return self._hold_current("resync_required")

        if self.mode in {ControlState.READY, ControlState.HOLD} and not self.auto_track_after_sync:
            self.last_result = ControllerResult(
                state=self.mode,
                commands=self.controller.hold_position(),
                reason=self.last_result.reason if self.mode is ControlState.HOLD else "ready",
                hold_position=self.controller.hold_position(),
            )
            return self.last_result

        validation_error = self._validate_sample(sample=sample, now=now)
        if validation_error is not None:
            self.resync_required = True
            return self._hold_current(validation_error)

        self.io_failure_count = 0
        self.controller.robot_synced = True
        result = self.controller.update(
            sample=sample,
            motor_positions=motor_positions,
            now=now,
        )
        self.mode = result.state
        self.last_result = result
        return result

    def get_status(self):
        state = self.last_result.state if self.last_result else self.mode
        tracking_active = bool(
            self.auto_track_after_sync
            and not self.fault_latched
            and state in {ControlState.CENTERING, ControlState.SYNCING, ControlState.TRACKING, ControlState.HOLD}
        )
        return RuntimeStatus(
            state=state,
            tracking_active=tracking_active,
            tracking_paused=bool(tracking_active and state is ControlState.HOLD),
            calibration_ready=bool(self.controller.robot_synced and not self.resync_required),
            fault_latched=self.fault_latched,
            reason=self.last_result.reason if self.last_result else "",
        )

    def _sync(self, sample, motor_positions, now):
        validation_error = self._validate_sample(sample=sample, now=now)
        if validation_error is not None:
            self.resync_required = True
            return self._hold_current(validation_error)

        if self.sync_pose_override is None:
            robot_pose = (
                self.controller.steps_to_radians(motor_positions[self.controller.yaw_motor_id], axis="yaw"),
                self.controller.steps_to_radians(motor_positions[self.controller.pitch_motor_id], axis="pitch"),
            )
        else:
            robot_pose = self.sync_pose_override
        self.controller.retargeter.sync_to_robot_pose(
            sample.head_pose_matrix,
            robot_pose=robot_pose,
            base_imu_rpy=sample.base_imu_rpy,
        )
        self.controller.robot_synced = True
        self.controller.last_commands = {
            self.controller.yaw_motor_id: int(motor_positions[self.controller.yaw_motor_id]),
            self.controller.pitch_motor_id: int(motor_positions[self.controller.pitch_motor_id]),
        }
        self.controller.last_command_deltas = {
            self.controller.yaw_motor_id: 0,
            self.controller.pitch_motor_id: 0,
        }
        self.io_failure_count = 0
        self.resync_required = False
        self.mode = ControlState.TRACKING if self.auto_track_after_sync else ControlState.READY
        self.last_result = ControllerResult(
            state=self.mode,
            commands=dict(self.controller.last_commands),
            reason="auto_synced",
            hold_position=self.controller.hold_position(),
        )
        return self.last_result

    def _validate_sample(self, sample, now) -> Optional[str]:
        if sample is None:
            return "waiting_for_sample"
        if getattr(sample, "fresh", True) is False:
            return "stale_sample"
        sample_timestamp = sample.timestamp if sample.timestamp is not None else now
        if sample_timestamp is None:
            return "waiting_for_sample"
        if now is not None and now - sample_timestamp > self.controller.avp_timeout_sec:
            return "avp_timeout"

        mode = getattr(self.controller.retargeter, "base_imu_compensation_mode", "off")
        if mode != "off" and getattr(sample, "base_imu_rpy", None) is None:
            return "imu_unavailable"
        return None

    def _hold_current(self, reason):
        current_commands: Dict[int, int] = dict(self.controller.last_commands)
        if not current_commands:
            current_commands = self.controller.hold_position()
        self.mode = ControlState.HOLD
        self.last_result = ControllerResult(
            state=ControlState.HOLD,
            commands=dict(current_commands),
            reason=str(reason),
            hold_position=dict(current_commands),
        )
        self.controller.last_hold_commands = dict(current_commands)
        return self.last_result

    def _is_centered(self, motor_positions):
        return (
            abs(
                int(motor_positions[self.controller.yaw_motor_id])
                - int(self.tracking_start_positions[self.controller.yaw_motor_id])
            )
            <= self.centering_step_tolerance
            and abs(
                int(motor_positions[self.controller.pitch_motor_id])
                - int(self.tracking_start_positions[self.controller.pitch_motor_id])
            )
            <= self.centering_step_tolerance
        )
