import importlib
import os
import sys


root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)


class FakePortHandler:
    def __init__(self, port):
        self.port = port
        self.closed = False

    def openPort(self):
        return True

    def setBaudRate(self, _baudrate):
        return True

    def closePort(self):
        self.closed = True


class FakeGroupSyncWrite:
    def __init__(self, *_args, **_kwargs):
        pass

    def clearParam(self):
        return None

    def addParam(self, *_args, **_kwargs):
        return True

    def txPacket(self):
        return FakeDXLModule.COMM_SUCCESS


class FakePacketHandler:
    ping_responses = {}
    read_responses = {}
    read1_responses = {}
    read2_responses = {}
    txrx_errors = {}
    packet_errors = {}
    write1_responses = {}

    def __init__(self, _protocol_version):
        pass

    @classmethod
    def configure(
        cls,
        *,
        ping_responses=None,
        read_responses=None,
        read1_responses=None,
        read2_responses=None,
        txrx_errors=None,
        packet_errors=None,
        write1_responses=None,
    ):
        cls.ping_responses = {motor_id: list(values) for motor_id, values in (ping_responses or {}).items()}
        cls.read_responses = {motor_id: list(values) for motor_id, values in (read_responses or {}).items()}
        cls.read1_responses = {motor_id: list(values) for motor_id, values in (read1_responses or {}).items()}
        cls.read2_responses = {motor_id: list(values) for motor_id, values in (read2_responses or {}).items()}
        cls.txrx_errors = dict(txrx_errors or {})
        cls.packet_errors = dict(packet_errors or {})
        cls.write1_responses = {motor_id: list(values) for motor_id, values in (write1_responses or {}).items()}

    def ping(self, _port_handler, motor_id):
        queue = self.ping_responses.get(motor_id)
        if queue:
            return queue.pop(0)
        return 1234, FakeDXLModule.COMM_SUCCESS, 0

    def read4ByteTxRx(self, _port_handler, motor_id, _addr):
        queue = self.read_responses.get((motor_id, _addr))
        if queue:
            return queue.pop(0)
        queue = self.read_responses.get(motor_id)
        if queue:
            return queue.pop(0)
        return 2048, FakeDXLModule.COMM_SUCCESS, 0

    def read2ByteTxRx(self, _port_handler, motor_id, _addr):
        queue = self.read2_responses.get((motor_id, _addr))
        if queue:
            return queue.pop(0)
        queue = self.read2_responses.get(motor_id)
        if queue:
            return queue.pop(0)
        return 100, FakeDXLModule.COMM_SUCCESS, 0

    def read1ByteTxRx(self, _port_handler, motor_id, _addr):
        queue = self.read1_responses.get((motor_id, _addr))
        if queue:
            return queue.pop(0)
        queue = self.read1_responses.get(motor_id)
        if queue:
            return queue.pop(0)
        return 25, FakeDXLModule.COMM_SUCCESS, 0

    def write1ByteTxRx(self, _port_handler, motor_id, _addr, _value):
        queue = self.write1_responses.get(motor_id)
        if queue:
            return queue.pop(0)
        return FakeDXLModule.COMM_SUCCESS, 0

    def getTxRxResult(self, code):
        return self.txrx_errors.get(code, f"comm:{code}")

    def getRxPacketError(self, code):
        return self.packet_errors.get(code, f"packet:{code}")


class FakeDXLModule:
    COMM_SUCCESS = 0
    PortHandler = FakePortHandler
    GroupSyncWrite = FakeGroupSyncWrite

    @staticmethod
    def PacketHandler(protocol_version):
        return FakePacketHandler(protocol_version)


def load_motor_module(
    monkeypatch,
    *,
    ping_responses=None,
    read_responses=None,
    read1_responses=None,
    read2_responses=None,
    txrx_errors=None,
    packet_errors=None,
    write1_responses=None,
):
    FakePacketHandler.configure(
        ping_responses=ping_responses,
        read_responses=read_responses,
        read1_responses=read1_responses,
        read2_responses=read2_responses,
        txrx_errors=txrx_errors,
        packet_errors=packet_errors,
        write1_responses=write1_responses,
    )
    monkeypatch.setitem(sys.modules, "dynamixel_sdk", FakeDXLModule)
    sys.modules.pop("src.hardware.motor", None)
    return importlib.import_module("src.hardware.motor")


def test_validate_motors_retries_until_position_read_succeeds(monkeypatch):
    motor = load_motor_module(
        monkeypatch,
        ping_responses={
            1: [(1234, 0, 0), (1234, 0, 0), (1234, 0, 0)],
            2: [(1234, 0, 0)],
        },
        read_responses={
            1: [(0, -3001, 0), (0, -3001, 0), (2048, 0, 0)],
            2: [(2048, 0, 0)],
        },
        txrx_errors={-3001: "COMM_RX_TIMEOUT"},
    )
    sleep_calls = []
    monkeypatch.setattr(motor.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    controller = motor.MotorController("/dev/ttyUSB0", 57600)

    ready = controller.validate_motors(
        (1, 2),
        retries=5,
        initial_delay_sec=0.2,
        retry_delay_sec=0.1,
    )

    assert ready is True
    assert controller.motors_ready is True
    assert controller.motor_error == ""
    assert sleep_calls == [0.2, 0.1, 0.1]


def test_validate_motors_reports_ping_stage_with_sdk_error(monkeypatch):
    motor = load_motor_module(
        monkeypatch,
        ping_responses={
            1: [(0, -3001, 0), (0, -3001, 0)],
        },
        txrx_errors={-3001: "COMM_RX_TIMEOUT"},
    )
    monkeypatch.setattr(motor.time, "sleep", lambda _seconds: None)

    controller = motor.MotorController("/dev/ttyUSB0", 57600)

    ready = controller.validate_motors(
        (1,),
        retries=2,
        initial_delay_sec=0.0,
        retry_delay_sec=0.05,
    )

    assert ready is False
    assert controller.motors_ready is False
    assert "无法 ping 通电机 ID 1" in controller.motor_error
    assert "COMM_RX_TIMEOUT" in controller.motor_error


def test_validate_motors_reports_position_read_stage_with_packet_error(monkeypatch):
    motor = load_motor_module(
        monkeypatch,
        ping_responses={
            1: [(1234, 0, 0)],
        },
        read_responses={
            1: [(0, 0, 4)],
        },
        packet_errors={4: "CRC error"},
    )
    monkeypatch.setattr(motor.time, "sleep", lambda _seconds: None)

    controller = motor.MotorController("/dev/ttyUSB0", 57600)

    ready = controller.validate_motors(
        (1,),
        retries=1,
        initial_delay_sec=0.0,
        retry_delay_sec=0.05,
    )

    assert ready is False
    assert controller.motors_ready is False
    assert "无法读取电机 ID 1 的当前位置" in controller.motor_error
    assert "CRC error" in controller.motor_error


def test_read_detailed_status_with_error_reports_position_stage_with_sdk_detail(monkeypatch):
    motor = load_motor_module(
        monkeypatch,
        read_responses={
            2: [(0, -3001, 0)],
        },
        txrx_errors={-3001: "COMM_RX_TIMEOUT"},
    )

    controller = motor.MotorController("/dev/ttyUSB0", 57600)

    status, error = controller.read_detailed_status_with_error(2)

    assert status is None
    assert error == "无法读取电机 ID 2 的当前位置：COMM_RX_TIMEOUT"


def test_enable_torque_returns_write_stage_error(monkeypatch):
    motor = load_motor_module(
        monkeypatch,
        write1_responses={
            2: [(-3001, 0)],
        },
        txrx_errors={-3001: "COMM_RX_TIMEOUT"},
    )

    controller = motor.MotorController("/dev/ttyUSB0", 57600)

    ok, error = controller.enable_torque(2, False)

    assert ok is False
    assert error == "无法关闭电机 ID 2 的扭矩：COMM_RX_TIMEOUT"


def test_probe_motor_reports_ping_stage_details(monkeypatch):
    motor = load_motor_module(
        monkeypatch,
        ping_responses={
            2: [(0, -3001, 0)],
        },
        txrx_errors={-3001: "COMM_RX_TIMEOUT"},
    )

    controller = motor.MotorController("/dev/ttyUSB0", 57600)

    probe = controller.probe_motor(2)

    assert probe["motor_id"] == 2
    assert probe["ping_ok"] is False
    assert probe["failed_stage"] == "ping"
    assert probe["sdk_error"] == "COMM_RX_TIMEOUT"
    assert probe["status_reads"] == {}


def test_probe_motor_reports_first_failed_register_and_status_reads(monkeypatch):
    motor = load_motor_module(
        monkeypatch,
        ping_responses={
            2: [(1234, 0, 0)],
        },
        read_responses={
            (2, 132): [(2048, 0, 0)],
            (2, 128): [(0, -3001, 0)],
        },
        read2_responses={
            (2, 126): [(120, 0, 0)],
            (2, 144): [(125, 0, 0)],
        },
        read1_responses={
            (2, 146): [(32, 0, 0)],
        },
        txrx_errors={-3001: "COMM_RX_TIMEOUT"},
    )

    controller = motor.MotorController("/dev/ttyUSB0", 57600)

    probe = controller.probe_motor(2)

    assert probe["ping_ok"] is True
    assert probe["present_position"] == 2048
    assert probe["failed_stage"] == "present_velocity"
    assert probe["sdk_error"] == "COMM_RX_TIMEOUT"
    assert probe["status_reads"]["present_position"]["ok"] is True
    assert probe["status_reads"]["present_velocity"]["ok"] is False
    assert probe["status_reads"]["present_velocity"]["address"] == 128
    assert probe["status_reads"]["present_velocity"]["bytes"] == 4
    assert probe["status_reads"]["present_velocity"]["error"] == "COMM_RX_TIMEOUT"
