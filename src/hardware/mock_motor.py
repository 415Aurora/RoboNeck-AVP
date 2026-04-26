class MockMotorController:
    """
    Mock Motor Controller for testing without hardware.
    """
    def __init__(self, port="", baudrate=0):
        self.connected = True
        self.motors_ready = True
        self.motor_error = ""
        print("[Mock] Motor Controller Initialized")
        self.mock_pos = {1: 2048, 2: 2048}

    def close(self):
        print("[Mock] Closed")
        self.connected = False
        self.motors_ready = False
        self.motor_error = "串口已关闭。"

    def enable_torque(self, motor_id, enable=True):
        print(f"[Mock] Torque {'Enable' if enable else 'Disable'} ID {motor_id}")

    def read_detailed_status(self, motor_id):
        import random
        return {
            "position": self.mock_pos.get(motor_id, 2048),
            "velocity": random.uniform(0, 10),
            "current": random.uniform(0, 100),
            "voltage": 11.1,
            "temperature": 35
        }
    
    def read_status(self, motor_id):
        s = self.read_detailed_status(motor_id)
        return {"voltage": s["voltage"], "temperature": s["temperature"]}

    def set_goal_positions(self, id_pos_dict):
        for mid, pos in id_pos_dict.items():
            self.mock_pos[mid] = int(pos)
        print(f"[Mock] Set Goal: {id_pos_dict}")

    def set_goal_position(self, mid, pos):
         self.mock_pos[mid] = int(pos)

    def set_pid(self, mid, p, i, d):
        print(f"[Mock] Set PID ID {mid}: {p} {i} {d}")

    def set_goal_pwm(self, mid, limit):
        print(f"[Mock] Set PWM Limit ID {mid}: {limit}")

    def set_profile(self, mid, v, a):
        print(f"[Mock] Set Profile ID {mid}: V={v} A={a}")

    def set_operating_mode(self, mid, mode):
        print(f"[Mock] Set Operating Mode ID {mid}: mode={mode}")
    
    def reboot(self, mid):
        print(f"[Mock] Reboot ID {mid}")
    
    def get_present_position(self, mid):
        return self.mock_pos.get(mid, 2048)

    def set_motor_readiness(self, ready, error=""):
        self.motors_ready = bool(ready)
        self.motor_error = "" if ready else str(error)

    def validate_motors(self, motor_ids, retries=3):
        for motor_id in motor_ids:
            if self.get_present_position(motor_id) is None:
                self.set_motor_readiness(False, f"无法读取电机 ID {motor_id} 的当前位置。")
                return False
        self.set_motor_readiness(True, "")
        return True
