from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple

import numpy as np
from src.utils.orientation import extract_avp_head_angles


class ControlState(Enum):
    INIT = "init"
    READY = "ready"
    CENTERING = "centering"
    SYNCING = "syncing"
    WAIT_FOR_AVP = "wait_for_avp"
    CALIBRATING = "calibrating"
    TRACKING = "tracking"
    HOLD = "hold"
    STOPPING = "stopping"
    FAULT = "fault"


@dataclass
class HeadPoseSample:
    head_pose_matrix: np.ndarray
    timestamp: float
    base_imu_rpy: Optional[Tuple[float, float, float]] = None
    raw_payload: Optional[dict] = None
    fresh: bool = True
    source_timestamp: Optional[float] = None


@dataclass
class ControllerResult:
    state: ControlState
    commands: Dict[int, int]
    reason: str = ""
    yaw_target_rad: Optional[float] = None
    pitch_target_rad: Optional[float] = None
    hold_position: Dict[int, int] = field(default_factory=dict)


class NeckController:
    def __init__(
        self,
        yaw_motor_id,
        pitch_motor_id,
        zero_pos,
        steps_per_rev,
        yaw_limit_deg,
        pitch_limit_deg,
        yaw_scale,
        pitch_scale,
        initial_pose,
        max_step_change,
        avp_timeout_sec,
        retargeter,
        yaw_deadzone_deg=0.0,
        pitch_deadzone_deg=0.0,
        centering_max_step_change=None,
        yaw_center_step=None,
        pitch_center_step=None,
        yaw_limit_steps=None,
        pitch_limit_steps=None,
        max_accel_step_change=None,
    ):
        self.yaw_motor_id = yaw_motor_id
        self.pitch_motor_id = pitch_motor_id
        self.zero_pos = zero_pos
        self.steps_per_rev = steps_per_rev
        self.yaw_limit_deg = tuple(yaw_limit_deg)
        self.pitch_limit_deg = tuple(pitch_limit_deg)
        self.yaw_scale = yaw_scale
        self.pitch_scale = pitch_scale
        self.initial_pose = initial_pose
        self.max_step_change = max_step_change
        self.avp_timeout_sec = avp_timeout_sec
        self.retargeter = retargeter
        self.yaw_deadzone_deg = yaw_deadzone_deg
        self.pitch_deadzone_deg = pitch_deadzone_deg
        self.centering_max_step_change = centering_max_step_change or max_step_change
        self.max_accel_step_change = max_step_change if max_accel_step_change is None else int(max_accel_step_change)
        self.yaw_center_step = zero_pos if yaw_center_step is None else int(yaw_center_step)
        self.pitch_center_step = zero_pos if pitch_center_step is None else int(pitch_center_step)
        self.yaw_limit_steps = None
        self.pitch_limit_steps = None
        if yaw_limit_steps is not None and pitch_limit_steps is not None:
            self.set_step_limits(
                yaw_limit_steps[0],
                yaw_limit_steps[1],
                pitch_limit_steps[0],
                pitch_limit_steps[1],
            )

        self.state = ControlState.INIT
        self.last_valid_timestamp = None
        self.last_commands = {}
        self.last_hold_commands = {}
        self.last_command_deltas = {}
        self.robot_synced = False
        self.last_reason = "init"

    def update(self, sample, motor_positions, now):
        if sample is None:
            return self._handle_missing_sample(now)

        sample_timestamp = sample.timestamp if sample.timestamp is not None else now
        if now - sample_timestamp > self.avp_timeout_sec:
            self.last_valid_timestamp = sample_timestamp
            return self._enter_hold("avp_timeout")

        self.last_valid_timestamp = sample_timestamp

        if not self.robot_synced:
            return self._calibrate_to_robot(sample, motor_positions)

        try:
            yaw_target, pitch_target = self.retargeter.compute_neck_target(
                sample.head_pose_matrix,
                base_imu_rpy=sample.base_imu_rpy,
            )
            return self.update_neck_target((yaw_target, pitch_target), motor_positions=motor_positions, reason="tracking")
        except Exception as exc:
            self.state = ControlState.FAULT
            self.last_reason = str(exc)
            return ControllerResult(state=self.state, commands={}, reason=self.last_reason)

    def update_neck_target(self, neck_target, motor_positions, reason="tracking", state_override=ControlState.TRACKING):
        if neck_target is None:
            return self._enter_hold(reason)

        yaw_target, pitch_target = neck_target
        commands = self._build_tracking_motor_commands(
            yaw_target,
            pitch_target,
            motor_positions,
            max_step_change=self.centering_max_step_change if state_override is ControlState.CENTERING else self.max_step_change,
        )
        self.last_commands = commands or dict(self.last_commands)
        self.state = state_override
        self.last_reason = reason
        return ControllerResult(
            state=self.state,
            commands=commands,
            reason=self.last_reason,
            yaw_target_rad=yaw_target,
            pitch_target_rad=pitch_target,
            hold_position=dict(self.last_hold_commands),
        )

    def update_step_targets(
        self,
        target_positions,
        motor_positions,
        reason="centering",
        state_override=ControlState.CENTERING,
        max_step_change=None,
    ):
        commands = self._build_step_motor_commands(
            target_positions=target_positions,
            motor_positions=motor_positions,
            max_step_change=self.centering_max_step_change if max_step_change is None else max_step_change,
        )
        self.last_commands = commands or dict(self.last_commands)
        self.state = state_override
        self.last_reason = reason
        return ControllerResult(
            state=self.state,
            commands=commands,
            reason=self.last_reason,
            hold_position=dict(self.last_hold_commands),
        )

    def hold_position(self):
        return dict(self.last_hold_commands or self.last_commands)

    def set_mechanical_center(self, yaw_center_step, pitch_center_step):
        self.yaw_center_step = int(yaw_center_step)
        self.pitch_center_step = int(pitch_center_step)

    def set_step_limits(self, yaw_min_step, yaw_max_step, pitch_min_step, pitch_max_step):
        self.yaw_limit_steps = (int(yaw_min_step), int(yaw_max_step))
        self.pitch_limit_steps = (int(pitch_min_step), int(pitch_max_step))

    def trigger_recalibration(self):
        self.robot_synced = False
        self.state = ControlState.CALIBRATING
        self.last_reason = "recalibration_requested"
        self.retargeter.trigger_calibration()

    def reset_calibration(self):
        self.robot_synced = False
        self.state = ControlState.CALIBRATING
        self.last_reason = "calibration_reset"
        self.retargeter.reset_calibration()

    def _handle_missing_sample(self, now):
        if self.last_valid_timestamp is None:
            self.state = ControlState.WAIT_FOR_AVP
            self.last_reason = "waiting_for_sample"
            return ControllerResult(state=self.state, commands={}, reason=self.last_reason)

        if now - self.last_valid_timestamp > self.avp_timeout_sec:
            return self._enter_hold("avp_timeout")

        return self._enter_hold("sample_missing")

    def _enter_hold(self, reason):
        self.state = ControlState.HOLD
        self.last_reason = reason
        self.last_hold_commands = dict(self.last_commands)
        if self.last_hold_commands:
            self.last_command_deltas = {motor_id: 0 for motor_id in self.last_hold_commands}
        return ControllerResult(
            state=self.state,
            commands=dict(self.last_hold_commands),
            reason=self.last_reason,
            hold_position=dict(self.last_hold_commands),
        )

    def _calibrate_to_robot(self, sample, motor_positions):
        avp_yaw, avp_pitch = self._extract_avp_angles(sample.head_pose_matrix)
        robot_yaw = self.steps_to_radians(motor_positions.get(self.yaw_motor_id, self.yaw_center_step), axis="yaw")
        robot_pitch = self.steps_to_radians(motor_positions.get(self.pitch_motor_id, self.pitch_center_step), axis="pitch")
        self.retargeter.sync_offsets(avp_yaw, avp_pitch, robot_yaw, robot_pitch)
        self.robot_synced = True
        self.state = ControlState.TRACKING
        self.last_reason = "calibrated"
        self.last_commands = {
            self.yaw_motor_id: motor_positions.get(self.yaw_motor_id, self.zero_pos),
            self.pitch_motor_id: motor_positions.get(self.pitch_motor_id, self.zero_pos),
        }
        self.last_command_deltas = {self.yaw_motor_id: 0, self.pitch_motor_id: 0}
        return ControllerResult(
            state=self.state,
            commands=dict(self.last_commands),
            reason=self.last_reason,
            hold_position=dict(self.last_hold_commands),
        )

    def _build_tracking_motor_commands(self, yaw_target, pitch_target, motor_positions, max_step_change=None):
        commands = {}
        if max_step_change is None:
            max_step_change = self.max_step_change
        yaw_command = yaw_target * self.yaw_scale
        pitch_command = pitch_target * self.pitch_scale

        yaw_deg = np.rad2deg(yaw_command)
        pitch_deg = np.rad2deg(pitch_command)

        if abs(yaw_deg) < self.yaw_deadzone_deg:
            yaw_command = 0.0
            yaw_deg = 0.0

        if abs(pitch_deg) < self.pitch_deadzone_deg:
            pitch_command = 0.0
            pitch_deg = 0.0

        yaw_deg = float(max(self.yaw_limit_deg[0], min(self.yaw_limit_deg[1], yaw_deg)))
        pitch_deg = float(max(self.pitch_limit_deg[0], min(self.pitch_limit_deg[1], pitch_deg)))
        yaw_target_steps = self._clamp_target_steps("yaw", self._rad_to_steps(np.deg2rad(yaw_deg), axis="yaw"))
        pitch_target_steps = self._clamp_target_steps("pitch", self._rad_to_steps(np.deg2rad(pitch_deg), axis="pitch"))

        commands[self.yaw_motor_id] = self._apply_motion_limit(
            self.yaw_motor_id,
            yaw_target_steps,
            motor_positions.get(self.yaw_motor_id, self.zero_pos),
            max_step_change=max_step_change,
        )
        commands[self.pitch_motor_id] = self._apply_motion_limit(
            self.pitch_motor_id,
            pitch_target_steps,
            motor_positions.get(self.pitch_motor_id, self.zero_pos),
            max_step_change=max_step_change,
        )

        return commands

    def _build_step_motor_commands(self, target_positions, motor_positions, max_step_change=None):
        commands = {}
        if max_step_change is None:
            max_step_change = self.centering_max_step_change
        commands[self.yaw_motor_id] = self._apply_motion_limit(
            self.yaw_motor_id,
            self._clamp_target_steps("yaw", target_positions[self.yaw_motor_id]),
            motor_positions.get(self.yaw_motor_id, self.yaw_center_step),
            max_step_change=max_step_change,
        )
        commands[self.pitch_motor_id] = self._apply_motion_limit(
            self.pitch_motor_id,
            self._clamp_target_steps("pitch", target_positions[self.pitch_motor_id]),
            motor_positions.get(self.pitch_motor_id, self.pitch_center_step),
            max_step_change=max_step_change,
        )
        return commands

    def _apply_motion_limit(self, motor_id, target_steps, fallback_position, max_step_change=None):
        if max_step_change is None:
            max_step_change = self.max_step_change
        previous = self.last_commands.get(motor_id, fallback_position)
        previous_delta = self.last_command_deltas.get(motor_id, 0)
        delta = int(target_steps) - int(previous)
        delta = int(max(-max_step_change, min(max_step_change, delta)))

        accel_limit = int(max(0, self.max_accel_step_change))
        min_delta = previous_delta - accel_limit
        max_delta = previous_delta + accel_limit
        delta = int(max(min_delta, min(max_delta, delta)))
        delta = int(max(-max_step_change, min(max_step_change, delta)))

        command = int(previous + delta)
        self.last_command_deltas[motor_id] = delta
        return command

    def _rad_to_steps(self, rad, axis="yaw"):
        steps_from_center = rad * (self.steps_per_rev / (2 * np.pi))
        center_step = self.yaw_center_step if axis == "yaw" else self.pitch_center_step
        target = center_step + steps_from_center
        return int(max(0, min(self.steps_per_rev - 1, target)))

    def _clamp_target_steps(self, axis, target_step):
        if axis == "yaw" and self.yaw_limit_steps is not None:
            min_step, max_step = self.yaw_limit_steps
            return int(max(min_step, min(max_step, int(target_step))))
        if axis == "pitch" and self.pitch_limit_steps is not None:
            min_step, max_step = self.pitch_limit_steps
            return int(max(min_step, min(max_step, int(target_step))))
        return int(target_step)

    def steps_to_radians(self, steps, axis="yaw"):
        center_step = self.yaw_center_step if axis == "yaw" else self.pitch_center_step
        return (steps - center_step) * ((2 * np.pi) / self.steps_per_rev)

    def _extract_avp_angles(self, head_pose_mat):
        rotation_matrix = head_pose_mat[:3, :3] if head_pose_mat.shape == (4, 4) else head_pose_mat
        return extract_avp_head_angles(rotation_matrix)
