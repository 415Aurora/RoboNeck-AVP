class MotorAdapter:
    def __init__(
        self,
        motor_io,
        yaw_motor_id,
        pitch_motor_id,
        enable_profiles=False,
        profile_velocity=0,
        profile_acceleration=500,
        position_mode=3,
    ):
        self.motor_io = motor_io
        self.yaw_motor_id = yaw_motor_id
        self.pitch_motor_id = pitch_motor_id
        self.enable_profiles = enable_profiles
        self.profile_velocity = profile_velocity
        self.profile_acceleration = profile_acceleration
        self.position_mode = position_mode

    def initialize(self):
        for motor_id in (self.yaw_motor_id, self.pitch_motor_id):
            self.motor_io.enable_torque(motor_id, False)
            self.motor_io.set_operating_mode(motor_id, self.position_mode)

        self.motor_io.set_goal_positions(self.get_present_positions())

        for motor_id in (self.yaw_motor_id, self.pitch_motor_id):
            self.motor_io.enable_torque(motor_id, True)

        if self.enable_profiles and hasattr(self.motor_io, "set_profile"):
            self.motor_io.set_profile(self.yaw_motor_id, velocity=self.profile_velocity, acceleration=self.profile_acceleration)
            self.motor_io.set_profile(self.pitch_motor_id, velocity=self.profile_velocity, acceleration=self.profile_acceleration)

    def get_present_positions(self):
        yaw_position = self.motor_io.get_present_position(self.yaw_motor_id)
        pitch_position = self.motor_io.get_present_position(self.pitch_motor_id)
        if yaw_position is None or pitch_position is None:
            raise RuntimeError("failed to read present position from one or more motors")
        return {
            self.yaw_motor_id: int(yaw_position),
            self.pitch_motor_id: int(pitch_position),
        }

    def send_commands(self, commands):
        if commands:
            self.motor_io.set_goal_positions(commands)

    def stop(self):
        self.motor_io.enable_torque(self.yaw_motor_id, False)
        self.motor_io.enable_torque(self.pitch_motor_id, False)
        self.motor_io.close()
