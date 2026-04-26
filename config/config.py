


"""
RoboNeck-AVP 配置文件。

包含 AVP 连接、视频流设置、电机配置以及控制参数。
"""

# AVP 配置
#AVP_IP = "100.78.18.15"  # 请更新为您的 AVP IP 地址。确保 AVP 与 PC 在同一网络下。
AVP_IP = "172.20.10.2"  # 请更新为您的 AVP IP 地址。确保 AVP 与 PC 在同一网络下。
# AVP_IP = "192.168.69.130"  # 请更新为您的 AVP IP 地址。确保 AVP 与 PC 在同一网络下。

# 视频流配置 (ZED Mini 摄像头)
ENABLE_VIDEO = True         # 是否启用视频流功能
ZED_CAMERA_ID = 0           # ZED UVC 摄像头的设备 ID (尝试更换为f 1)
STREAM_RESOLUTION = "3840x1080"  # 视频分辨率 (Default Stereo 1080p)
STREAM_FPS = 30             # 视频帧率 (Hz)
USE_DUMMY_VIDEO_IF_NO_CAMERA = False # 如果未找到摄像头，是否启用虚拟测试图案

# ZED SDK 配置
USE_ZED_SDK = True          # 设置为 True 以使用 ZED SDK (获取 IMU 数据)
ZED_RESOLUTION = "HD1080"    # ZED SDK 分辨率: HD720 (60fps), HD1080 (30fps), HD2K (15fps)
ZED_IMU_COMPENSATION_MODE = "off"  # off / pitch_only / yaw_pitch

# Dynamixel 电机配置
# 使用 `ls /dev/ttyUSB*` 检查您的设备端口
DYNAMIXEL_PORT = '/dev/ttyUSB0' # 串口设备路径
BAUDRATE = 57600              # 波特率 (wizard软件检查电机设置)
PROTOCOL_VERSION = 2.0          # Dynamixel 协议版本 (X 系列通常为 2.0)

# 电机 ID
YAW_MOTOR_ID = 1    # 偏航轴 (Yaw) 电机 ID
PITCH_MOTOR_ID = 2  # 俯仰轴 (Pitch) 电机 ID

# 控制参数
# 缩放因子：1.0 表示头部角度到电机角度的 1:1 映射
# 增大 > 1.0 会放大动作，减小 < 1.0 会缩小动作
YAW_SCALE = 2 
PITCH_SCALE = 1.0

# 角度限制（单位：度）
# Dynamixel 使用 0-4096 的步进值，此处以度为单位设置软限位
# 假设 0 度为中心位置 (对应电机步进 2048)

YAW_LIMIT_DEG = [-180, 180]     # 偏航角限制范围
PITCH_LIMIT_DEG = [-180, 180]   # 俯仰角限制范围

# 循环频率
LOOP_RATE = 60 # 主控制循环频率 (Hz) - Increased to 60Hz for smoother tracking

# 平滑参数 (Exponential Moving Average)
# Alpha (0.0 - 1.0): 较小的值 = 更强的平滑 (更多的延迟); 较大的值 = 更快的响应
SMOOTHING_ALPHA = 0.4

# 控制安全参数
AVP_TIMEOUT_SEC = 0.25          # 超过该时间未收到新头姿，则进入 HOLD
MAX_STEP_CHANGE = 120           # 每个控制周期允许的最大步进变化
CENTERING_MAX_STEP_CHANGE = 64  # 回中阶段每个控制周期允许的最大步进变化
MAX_COMMAND_ACCEL_STEP = 32     # 相邻控制周期最大步进变化增量，抑制突变加速度
CENTERING_STEP_TOLERANCE = 8    # 回中完成判定的步进容差
CENTERING_FINAL_STEP_TOLERANCE = 3  # 回中最终稳定判定的步进容差
CENTERING_SETTLE_TICKS = 2      # 连续满足最终稳定容差的采样次数
CENTERING_TIMEOUT_SEC = 5.0     # 回中阶段最大允许耗时（秒）
STATUS_PRINT_INTERVAL = 1.0     # 控制台状态打印周期（秒）
YAW_DEADZONE_DEG = 3.0          # 小角度偏航死区，避免高频抖动
PITCH_DEADZONE_DEG = 3.0        # 小角度俯仰死区，避免高频抖动
CENTER_TOLERANCE_DEG = 3.0      # 机械回中判定阈值
IO_FAULT_THRESHOLD = 3          # 连续电机读写失败达到该次数后进入 FAULT
GUI_MOTOR_READY_FAIL_TICKS = 3  # GUI 监控连续失败达到该次数后才判未就绪
GUI_MOTOR_READY_RECOVER_TICKS = 2  # GUI 监控连续成功达到该次数后才恢复就绪
TRACKING_PROFILE_VELOCITY = 0   # 连接后默认跟踪 Profile Velocity
TRACKING_PROFILE_ACCELERATION = 120  # 连接后默认跟踪 Profile Acceleration

# 初始化校准配置
ENABLE_INIT_CALIBRATION = True          # 是否在启动时执行初始化校准
INITIAL_POSE = {"yaw": 0.0, "pitch": 0.0} # 初始化姿态 (度)

# 模拟模式 (Mock Mode)
import os
def get_bool_env(name, default):
    val = os.getenv(name, str(default))
    return val.lower() in ('true', '1', 't')

MOCK_AVP = get_bool_env('MOCK_AVP', False)     # 设置为 True 以模拟 AVP 数据 (测试用)
MOCK_MOTORS = get_bool_env('MOCK_MOTORS', False)  # 设置为 True 以在未连接电机的情况下运行 (测试用)

# 电机规格 (Dynamixel X-series)
STEPS_PER_REV = 4096 # 每转步进数 (分辨率)
ZERO_POS = 2048      # 零位位置 (中心点)
