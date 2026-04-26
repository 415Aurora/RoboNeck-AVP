
import os
import time
try:
    import dynamixel_sdk as dxl
except ImportError:
    dxl = None
    print("Warning: dynamixel_sdk not found. Only mock mode will work.")
    
from config import config

class MotorController:
    """
    Dynamixel 电机控制类，用于管理电机连接、扭矩控制和位置命令。
    针对 Dynamixel XC330-T288-T 进行了适配。
    """
    # Control Table Addresses for XC330-T288-T / X-Series
    ADDR_OPERATING_MODE         = 11
    ADDR_TORQUE_ENABLE          = 64
    ADDR_LED                    = 65
    ADDR_STATUS_RETURN_LEVEL    = 68
    ADDR_POSITION_D_GAIN        = 80
    ADDR_POSITION_I_GAIN        = 82
    ADDR_POSITION_P_GAIN        = 84
    ADDR_GOAL_PWM               = 100
    ADDR_PROFILE_ACCELERATION   = 108
    ADDR_PROFILE_VELOCITY       = 112
    ADDR_GOAL_POSITION          = 116
    ADDR_PRESENT_CURRENT        = 126
    ADDR_PRESENT_VELOCITY       = 128
    ADDR_PRESENT_POSITION       = 132
    ADDR_PRESENT_INPUT_VOLTAGE  = 144
    ADDR_PRESENT_TEMPERATURE    = 146

    LEN_GOAL_POSITION           = 4
    LEN_PRESENT_POSITION        = 4
    PROBE_REGISTERS = (
        ("present_position", ADDR_PRESENT_POSITION, 4),
        ("present_velocity", ADDR_PRESENT_VELOCITY, 4),
        ("present_current", ADDR_PRESENT_CURRENT, 2),
        ("present_input_voltage", ADDR_PRESENT_INPUT_VOLTAGE, 2),
        ("present_temperature", ADDR_PRESENT_TEMPERATURE, 1),
    )

    def __init__(self, port, baudrate, protocol_version=2.0):
        """
        初始化电机控制器。

        Args:
            port (str): 串口设备路径。
            baudrate (int): 通信波特率。
            protocol_version (float, optional): Dynamixel 协议版本. 默认为 2.0.
        """
        self.port = port
        self.baudrate = baudrate
        self.protocol_version = protocol_version
        self.motors_ready = False
        self.motor_error = ""
        
        # 初始化 PortHandler 和 PacketHandler
        if dxl is None:
            print("Error: Dynamixel SDK not found. Motor functionality unavailable.")
            self.portHandler = None
            self.packetHandler = None
            self.groupSyncWrite = None
            self.connected = False
            return

        self.portHandler = dxl.PortHandler(port)
        self.packetHandler = dxl.PacketHandler(protocol_version)
        
        self.connected = False
        self.connect()
        
        # Initialize GroupSyncWrite
        if self.connected:
            self.groupSyncWrite = dxl.GroupSyncWrite(
                self.portHandler, self.packetHandler, self.ADDR_GOAL_POSITION, self.LEN_GOAL_POSITION
            )

    def connect(self):
        """
        建立与 Dynamixel 电机的串行连接。
        设置波特率并更新连接状态。
        """
        try:
            if self.portHandler.openPort():
                print(f"Succeeded to open the port {self.port}")
            else:
                print(f"Failed to open the port {self.port}")
                return

            if self.portHandler.setBaudRate(self.baudrate):
                print(f"Succeeded to change the baudrate to {self.baudrate}")
                self.connected = True
                self.set_motor_readiness(False, "")
            else:
                print(f"Failed to change the baudrate")
                return
        except Exception as e:
            print(f"Error connecting to Dynamixel: {e}")

    def set_motor_readiness(self, ready, error=""):
        self.motors_ready = bool(ready)
        self.motor_error = "" if ready else str(error)

    def _sdk_error_detail(self, dxl_comm_result=None, dxl_error=None):
        details = []
        if dxl_comm_result is not None and dxl_comm_result != dxl.COMM_SUCCESS:
            details.append(self.packetHandler.getTxRxResult(dxl_comm_result))
        if dxl_error not in (None, 0):
            details.append(self.packetHandler.getRxPacketError(dxl_error))
        return "；".join(detail for detail in details if detail)

    def _format_motor_readiness_error(self, prefix, motor_id, detail=""):
        message = f"{prefix} ID {motor_id}"
        if detail:
            return f"{message}：{detail}"
        return f"{message}。"

    def _ping_with_error(self, motor_id):
        if not self.connected:
            return None, "串口未连接。"
        model_number, dxl_comm_result, dxl_error = self.packetHandler.ping(self.portHandler, motor_id)
        if dxl_comm_result != dxl.COMM_SUCCESS or dxl_error != 0:
            return None, self._sdk_error_detail(dxl_comm_result, dxl_error)
        return model_number, ""

    def _read_register_with_error(self, motor_id, addr, n_bytes):
        if not self.connected:
            return None, "串口未连接。"

        if n_bytes == 1:
            value, res, err = self.packetHandler.read1ByteTxRx(self.portHandler, motor_id, addr)
        elif n_bytes == 2:
            value, res, err = self.packetHandler.read2ByteTxRx(self.portHandler, motor_id, addr)
        elif n_bytes == 4:
            value, res, err = self.packetHandler.read4ByteTxRx(self.portHandler, motor_id, addr)
        else:
            return None, f"不支持的寄存器长度：{n_bytes}"

        if res != dxl.COMM_SUCCESS or err != 0:
            return None, self._sdk_error_detail(res, err)
        return value, ""

    def _write_register_with_error(self, motor_id, addr, value, n_bytes):
        if not self.connected:
            return False, "串口未连接。"

        if n_bytes == 1:
            res, err = self.packetHandler.write1ByteTxRx(self.portHandler, motor_id, addr, int(value))
        elif n_bytes == 2:
            res, err = self.packetHandler.write2ByteTxRx(self.portHandler, motor_id, addr, int(value))
        elif n_bytes == 4:
            res, err = self.packetHandler.write4ByteTxRx(self.portHandler, motor_id, addr, int(value))
        else:
            return False, f"不支持的寄存器长度：{n_bytes}"

        if res != dxl.COMM_SUCCESS or err != 0:
            return False, self._sdk_error_detail(res, err)
        return True, ""

    def _read_present_position_with_error(self, motor_id):
        pos, error = self._read_register_with_error(motor_id, self.ADDR_PRESENT_POSITION, 4)
        if pos is None:
            return None, error

        if pos > 0x7FFFFFFF:
            pos -= 4294967296
        return pos, ""

    def _normalize_probe_value(self, stage_name, value):
        if value is None:
            return None
        if stage_name in {"present_position", "present_velocity"} and value > 0x7FFFFFFF:
            value -= 4294967296
        elif stage_name == "present_current" and value > 0x7FFF:
            value -= 65536

        if stage_name == "present_velocity":
            return value * 0.229
        if stage_name == "present_input_voltage":
            return value / 10.0
        return value

    def probe_motor(self, motor_id):
        """Read a structured diagnostic snapshot for a single motor."""
        probe = {
            "motor_id": int(motor_id),
            "connected": bool(self.connected),
            "ping_ok": False,
            "model_number": None,
            "present_position": None,
            "failed_stage": "",
            "sdk_error": "",
            "status_reads": {},
        }

        if not self.connected:
            probe["failed_stage"] = "not_connected"
            probe["sdk_error"] = "串口未连接。"
            return probe

        model_number, ping_error = self._ping_with_error(motor_id)
        if model_number is None:
            probe["failed_stage"] = "ping"
            probe["sdk_error"] = ping_error
            return probe

        probe["ping_ok"] = True
        probe["model_number"] = model_number

        for stage_name, addr, n_bytes in self.PROBE_REGISTERS:
            value, error = self._read_register_with_error(motor_id, addr, n_bytes)
            normalized_value = self._normalize_probe_value(stage_name, value)
            ok = value is not None
            probe["status_reads"][stage_name] = {
                "address": addr,
                "bytes": n_bytes,
                "ok": ok,
                "value": normalized_value if ok else None,
                "error": "" if ok else error,
            }
            if stage_name == "present_position" and ok:
                probe["present_position"] = normalized_value
            if (not ok) and not probe["failed_stage"]:
                probe["failed_stage"] = stage_name
                probe["sdk_error"] = error

        return probe

    def validate_motors(self, motor_ids, retries=3, initial_delay_sec=0.0, retry_delay_sec=0.0):
        if not self.connected:
            self.set_motor_readiness(False, "串口未连接。")
            return False

        retries = max(1, int(retries))
        initial_delay_sec = max(0.0, float(initial_delay_sec))
        retry_delay_sec = max(0.0, float(retry_delay_sec))
        if initial_delay_sec > 0:
            time.sleep(initial_delay_sec)

        for motor_id in motor_ids:
            for attempt in range(retries):
                model_number, ping_error = self._ping_with_error(motor_id)
                if model_number is None:
                    self.set_motor_readiness(
                        False,
                        self._format_motor_readiness_error("无法 ping 通电机", motor_id, ping_error),
                    )
                    if attempt < retries - 1 and retry_delay_sec > 0:
                        time.sleep(retry_delay_sec)
                    continue

                position, position_error = self._read_present_position_with_error(motor_id)
                if position is None:
                    position_message = f"无法读取电机 ID {motor_id} 的当前位置"
                    if position_error:
                        position_message = f"{position_message}：{position_error}"
                    else:
                        position_message = f"{position_message}。"
                    self.set_motor_readiness(
                        False,
                        position_message,
                    )
                    if attempt < retries - 1 and retry_delay_sec > 0:
                        time.sleep(retry_delay_sec)
                    continue
                break
            else:
                return False

        self.set_motor_readiness(True, "")
        return True

    def ping(self, motor_id):
        """
        Check if a motor is connected.
        Returns model_number if successful, None otherwise.
        """
        model_number, _error = self._ping_with_error(motor_id)
        return model_number

    def enable_torque(self, motor_id, enable=True):
        """
        启用或禁用指定 ID 电机的扭矩。
        Safety: Applies 'Soft Start' by syncing Goal Position to Present Position before enabling.
        """
        if not self.connected:
            return False, "串口未连接。"
        
        if enable:
            # --- Soft Start Strategy ---
            # 1. Read Present Position
            present_pos = self.get_present_position(motor_id)
            if present_pos is not None:
                # 2. Set Goal Position to Current Position (prevent Jump)
                self._write_register_with_error(motor_id, self.ADDR_GOAL_POSITION, present_pos, 4)
                print(f"[SoftStart] Synced ID {motor_id} Goal -> Present ({present_pos})")
            
        ok, error = self._write_register_with_error(
            motor_id,
            self.ADDR_TORQUE_ENABLE,
            1 if enable else 0,
            1,
        )
        action = "使能" if enable else "关闭"
        if not ok:
            message = f"无法{action}电机 ID {motor_id} 的扭矩"
            if error:
                message = f"{message}：{error}"
            print(message)
            return False, message

        print(f"Torque {'Enabled' if enable else 'Disabled'} for ID {motor_id}")
        return True, ""

    def set_profile(self, motor_id, velocity, acceleration):
        """
        设置运动曲线 (Profile) 参数，用于控制运动的平滑度。
        Address 112: Profile Velocity (0 = Infinite)
        Address 108: Profile Acceleration (0 = Infinite)
        """
        if not self.connected: return

        # Set Profile Velocity
        self.packetHandler.write4ByteTxRx(self.portHandler, motor_id, self.ADDR_PROFILE_VELOCITY, int(velocity))
        
        # Set Profile Acceleration
        self.packetHandler.write4ByteTxRx(self.portHandler, motor_id, self.ADDR_PROFILE_ACCELERATION, int(acceleration))
        
        print(f"Profile Set for ID {motor_id}: Vel={velocity}, Acc={acceleration}")

    def read_detailed_status(self, motor_id):
        """
        Read detailed status including Position, Velocity, Current, Voltage, Temp.
        Returns dict or None.
        """
        status, _error = self.read_detailed_status_with_error(motor_id)
        return status

    def read_detailed_status_with_error(self, motor_id):
        """Read detailed status and return (status, error_message)."""
        if not self.connected:
            return None, "串口未连接。"

        pos, pos_error = self._read_register_with_error(motor_id, self.ADDR_PRESENT_POSITION, 4)
        if pos is None:
            message = f"无法读取电机 ID {motor_id} 的当前位置"
            if pos_error:
                message = f"{message}：{pos_error}"
            else:
                message = f"{message}。"
            return None, message

        vel, _vel_error = self._read_register_with_error(motor_id, self.ADDR_PRESENT_VELOCITY, 4)
        curr, _curr_error = self._read_register_with_error(motor_id, self.ADDR_PRESENT_CURRENT, 2)
        volt, _volt_error = self._read_register_with_error(motor_id, self.ADDR_PRESENT_INPUT_VOLTAGE, 2)
        temp, _temp_error = self._read_register_with_error(motor_id, self.ADDR_PRESENT_TEMPERATURE, 1)

        if pos > 0x7FFFFFFF:
            pos -= 4294967296

        velocity = 0.0
        if vel is not None:
            if vel > 0x7FFFFFFF:
                vel -= 4294967296
            velocity = vel * 0.229

        current = 0.0
        if curr is not None:
            if curr > 0x7FFF:
                curr -= 65536
            current = curr * 1.0

        voltage = 0.0
        if volt is not None:
            voltage = volt / 10.0

        temperature = temp if temp is not None else 0

        return {
            "position": pos,
            "velocity": velocity, 
            "current": current,
            "voltage": voltage,
            "temperature": temperature
        }, ""

    def read_status(self, motor_id):
        """Legacy method for voltage/temp"""
        s = self.read_detailed_status(motor_id)
        if s:
            return {"voltage": s["voltage"], "temperature": s["temperature"]}
        return None

    def set_pid(self, motor_id, p, i, d):
        """Set PID Gains."""
        if not self.connected: return
        self.packetHandler.write2ByteTxRx(self.portHandler, motor_id, self.ADDR_POSITION_P_GAIN, int(p))
        self.packetHandler.write2ByteTxRx(self.portHandler, motor_id, self.ADDR_POSITION_I_GAIN, int(i))
        self.packetHandler.write2ByteTxRx(self.portHandler, motor_id, self.ADDR_POSITION_D_GAIN, int(d))
        print(f"Set PID for {motor_id}: {p}, {i}, {d}")
        
    def get_pid(self, motor_id):
        """Read PID Gains."""
        if not self.connected: return (0,0,0)
        p, _, _ = self.packetHandler.read2ByteTxRx(self.portHandler, motor_id, self.ADDR_POSITION_P_GAIN)
        i, _, _ = self.packetHandler.read2ByteTxRx(self.portHandler, motor_id, self.ADDR_POSITION_I_GAIN)
        d, _, _ = self.packetHandler.read2ByteTxRx(self.portHandler, motor_id, self.ADDR_POSITION_D_GAIN)
        return (p, i, d)

    def set_goal_pwm(self, motor_id, pwm_limit):
        """Set Goal PWM (Torque Limit proxy) or PWM Limit depending on mode.
           ADDR 100 is Goal PWM (in PWM mode) or Limit? 
           Actually Address 100 in X-series is "Goal PWM" used in PWM Control Mode.
           To limit Output in Position Mode, usually we change "Goal PWM" (which acts as limit).
           Range 0-885."""
        if not self.connected: return
        self.packetHandler.write2ByteTxRx(self.portHandler, motor_id, self.ADDR_GOAL_PWM, int(pwm_limit))
        print(f"Set Goal PWM (Limit) for {motor_id}: {pwm_limit}")

    def reboot(self, motor_id):
        """Reboot the motor to clear errors."""
        if not self.connected: return
        self.packetHandler.reboot(self.portHandler, motor_id)
        print(f"Reboot command sent to ID {motor_id}")

    def set_goal_positions(self, id_pos_dict):
        """
        同时设置多个电机的目标位置 (SyncWrite)。

        Args:
            id_pos_dict (dict): {motor_id: position_steps}
        """
        if not self.connected: return
        
        # 1. Clear previous parameters
        self.groupSyncWrite.clearParam()
        
        # 2. Add parameters for each motor
        for motor_id, position in id_pos_dict.items():
            param_goal_position = int(position).to_bytes(4, byteorder='little')
            param_list = list(param_goal_position)
            
            if not self.groupSyncWrite.addParam(motor_id, param_list):
                print(f"[ID:{motor_id}] groupSyncWrite addParam failed")
                return

        # 3. Transmit packet
        dxl_comm_result = self.groupSyncWrite.txPacket()
        if dxl_comm_result != dxl.COMM_SUCCESS:
             # print(f"SyncWrite Error: {self.packetHandler.getTxRxResult(dxl_comm_result)}")
             pass

    def close(self):
        """关闭串行端口连接。"""
        self.portHandler.closePort()
        self.connected = False
        self.set_motor_readiness(False, "串口已关闭。")
        print("Port closed.")

    def get_operating_mode(self, motor_id):
        """Read Operating Mode (Addr 11)."""
        if not self.connected: return None
        mode, res, err = self.packetHandler.read1ByteTxRx(self.portHandler, motor_id, self.ADDR_OPERATING_MODE)
        if res != dxl.COMM_SUCCESS:
             # print(self.packetHandler.getTxRxResult(res))
             return None
        return mode

    def set_operating_mode(self, motor_id, mode):
        """Set Operating Mode (Addr 11). Torque must be disabled first."""
        if not self.connected: return
        res, err = self.packetHandler.write1ByteTxRx(self.portHandler, motor_id, self.ADDR_OPERATING_MODE, mode)
        if res != dxl.COMM_SUCCESS:
            print(f"Set Mode Error {motor_id}: {self.packetHandler.getTxRxResult(res)}")
        elif err != 0:
            print(f"Set Mode Error {motor_id}: {self.packetHandler.getRxPacketError(err)}")
        else:
            print(f"Operating Mode set to {mode} for ID {motor_id}")

    def get_present_position(self, motor_id):
        """Read Present Position (Addr 132)."""
        pos, _error = self._read_present_position_with_error(motor_id)
        return pos
