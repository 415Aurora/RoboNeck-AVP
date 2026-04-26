
import sys
import os
import time

# Ensure the project root is in sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

try:
    import dynamixel_sdk as dxl
    HAS_SDK = True
except ImportError:
    HAS_SDK = False

from config import config
from src.hardware.motor import MotorController

DEVICENAME = config.DYNAMIXEL_PORT
PROTOCOL_VERSION = 2.0

# Common Baudrates to check
BAUDRATES = [57600, 1000000, 115200, 9600]


def _build_probe_controller(port_handler, packet_handler, baudrate):
    controller = MotorController.__new__(MotorController)
    controller.port = DEVICENAME
    controller.baudrate = baudrate
    controller.protocol_version = PROTOCOL_VERSION
    controller.motors_ready = False
    controller.motor_error = ""
    controller.portHandler = port_handler
    controller.packetHandler = packet_handler
    controller.groupSyncWrite = None
    controller.connected = True
    return controller


def format_probe_report(probe):
    parts = [
        f"motor_id={probe['motor_id']}",
        f"ping_ok={probe['ping_ok']}",
    ]
    model_number = probe.get("model_number")
    if model_number is not None:
        parts.append(f"model={model_number}")
    if probe.get("present_position") is not None:
        parts.append(f"present_position={probe['present_position']}")
    if probe.get("failed_stage"):
        parts.append(f"failed_stage={probe['failed_stage']}")
    if probe.get("sdk_error"):
        parts.append(f"sdk_error={probe['sdk_error']}")

    status_parts = []
    for stage_name, result in probe.get("status_reads", {}).items():
        addr = result["address"]
        n_bytes = result["bytes"]
        if result["ok"]:
            status_parts.append(f"{stage_name}@{addr}/{n_bytes}B={result['value']}")
        else:
            status_parts.append(f"{stage_name}@{addr}/{n_bytes}B=ERROR({result['error']})")
    if status_parts:
        parts.append("status_reads=" + ", ".join(status_parts))

    return " | ".join(parts)

def scan_motors():
    print("=== Dynamixel Motor Scanner ===")
    
    if not HAS_SDK:
        print("Error: dynamixel_sdk not found.")
        return

    portHandler = dxl.PortHandler(DEVICENAME)
    packetHandler = dxl.PacketHandler(PROTOCOL_VERSION)

    if not portHandler.openPort():
        print(f"Failed to open port {DEVICENAME}")
        return
    print(f"Opened port {DEVICENAME}")

    found_any = False

    for baud in BAUDRATES:
        print(f"\nScanning at {baud} bps...")
        if not portHandler.setBaudRate(baud):
            print(f"  Failed to set baudrate to {baud}")
            continue

        probe_controller = _build_probe_controller(portHandler, packetHandler, baud)
        
        # Try Broadcast Ping
        dxl_data_list, dxl_comm_result = packetHandler.broadcastPing(portHandler)
        if dxl_comm_result != dxl.COMM_SUCCESS:
            # Broadcast ping might fail if too many devices or noise, 
            # but usually it returns what it found before timeout.
            # If completely failed, print error.
            print(f"  Broadcast Ping Error: {packetHandler.getTxRxResult(dxl_comm_result)}")
        
        if dxl_data_list:
            print(f"  FOUND {len(dxl_data_list)} motors:")
            for dxl_id in dxl_data_list:
                model_num = dxl_data_list.get(dxl_id)[0]
                fw_ver = dxl_data_list.get(dxl_id)[1]
                print(f"    [ID:{dxl_id:03d}] Model: {model_num}, Firmware: {fw_ver}")
                print(f"      Probe: {format_probe_report(probe_controller.probe_motor(dxl_id))}")
                found_any = True
        else:
            print("  No motors found.")

    portHandler.closePort()
    print("\nScan Complete.")
    
    if not found_any:
        print("troubleshooting tips:")
        print("1. Check power supply (12V usually required).")
        print("2. Check data cable connections (daisy chain).")
        print("3. Ensure LEDs on motors blink once when powered on.")
        print("4. Try a single motor at a time.")

if __name__ == "__main__":
    scan_motors()
