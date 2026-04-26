# RoboNeck-AVP

中文 | [English](#english)

## 中文

### 项目简介

`RoboNeck-AVP` 将 Apple Vision Pro 头部姿态实时映射为双轴 Dynamixel 机械颈部控制指令，并提供本地 GUI 工具用于连接管理、校准和诊断。项目支持无硬件模拟模式，便于开发和回归测试。

### 核心能力

- Vision Pro 头姿采集与 yaw/pitch 重定向
- 运行时预检（依赖、串口、视频链路）
- 机械中心位保存/回滚与跟踪起始位管理
- 死区、软限位、步进约束与异常保持（`HOLD/FAULT`）
- PyQt6 操作台（主控、视频、校准、诊断）

### 项目结构

```text
RobotNeck-AVP/
├── config/        # 配置与校准
├── src/           # core / hardware / gui / utils
├── tests/         # 软件测试与硬件测试
├── README.md
├── requirements.txt
└── requirements-hardware.txt
```

### 环境准备

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-hardware.txt
pip install -e ../VisionProTeleop
```

### 运行与测试

主程序：

```bash
python src/main.py
```

GUI：

```bash
python src/gui/main.py
```

软件测试：

```bash
pytest -q
```

硬件测试（默认不会自动执行）：

```bash
pytest -q --run-hardware tests/test_avp_connection.py tests/test_camera.py tests/test_motor.py
```

无硬件模拟：

```bash
MOCK_AVP=1 MOCK_MOTORS=1 python src/main.py
```

### 配置说明

- 在 `config/config.py` 中设置 `AVP_IP`、`DYNAMIXEL_PORT`、相机参数和控制参数。
- 如果 `USE_ZED_SDK = True`，需单独安装 ZED SDK Python 绑定（`pyzed.sl` 不由 `pip` 提供）。
- 可通过环境变量覆盖标定文件路径：

```bash
ROBO_NECK_CALIBRATION_PATH=/abs/path/to/neck_calibration.json
```

### 故障排查顺序

1. 确认 `pip install -e ../VisionProTeleop` 成功，且 `avp_stream` 可导入。
2. 确认串口存在：`ls /dev/ttyUSB*`（按你的设备实际路径检查）。
3. 如启用视频，确认 `opencv-python` 已安装。
4. 如启用 ZED SDK，确认 `pyzed.sl` 可导入。
5. 使用 `--run-hardware` 重新执行对应硬件测试定位问题。

---

## English

### Overview

`RoboNeck-AVP` maps Apple Vision Pro head pose to a two-axis Dynamixel robotic neck in real time. It also provides a local GUI for connection management, calibration, and diagnostics. Mock modes are available for software-only development.

### Key Capabilities

- Vision Pro head-pose acquisition and yaw/pitch retargeting
- Runtime preflight checks (dependencies, serial port, video path)
- Mechanical center save/rollback and tracking start pose handling
- Deadzone, soft-limit, step constraint, and safe `HOLD/FAULT` behavior
- PyQt6 operator console (dashboard, streaming, calibration, diagnostics)

### Project Layout

```text
RobotNeck-AVP/
├── config/        # configuration and calibration
├── src/           # core / hardware / gui / utils
├── tests/         # software and hardware tests
├── README.md
├── requirements.txt
└── requirements-hardware.txt
```

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-hardware.txt
pip install -e ../VisionProTeleop
```

### Run and Test

Main app:

```bash
python src/main.py
```

GUI:

```bash
python src/gui/main.py
```

Software regression tests:

```bash
pytest -q
```

Hardware tests (explicit opt-in):

```bash
pytest -q --run-hardware tests/test_avp_connection.py tests/test_camera.py tests/test_motor.py
```

Mock run:

```bash
MOCK_AVP=1 MOCK_MOTORS=1 python src/main.py
```

### Configuration Notes

- Set `AVP_IP`, `DYNAMIXEL_PORT`, camera settings, and controller parameters in `config/config.py`.
- If `USE_ZED_SDK = True`, install ZED SDK Python bindings separately (`pyzed.sl` is not installed by `pip`).
- Override calibration path with:

```bash
ROBO_NECK_CALIBRATION_PATH=/abs/path/to/neck_calibration.json
```

### Troubleshooting Order

1. Ensure `pip install -e ../VisionProTeleop` succeeds and `avp_stream` can be imported.
2. Ensure the configured serial device exists (`/dev/ttyUSB*` or your actual device path).
3. If video is enabled, ensure `opencv-python` is installed.
4. If ZED mode is enabled, ensure `pyzed.sl` is importable.
5. Re-run the relevant hardware tests with `--run-hardware` to isolate AVP, camera, or motor issues.
