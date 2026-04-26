from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config import config
from src.gui.ui_state import derive_dashboard_state


class StatusCard(QGroupBox):
    def __init__(self, title, subtitle, parent=None):
        super().__init__(title, parent)
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.label_state = QLabel("Unknown")
        self.label_state.setObjectName("statusValue")
        self.label_detail = QLabel(subtitle)
        self.label_detail.setWordWrap(True)

        layout.addWidget(self.label_state)
        layout.addWidget(self.label_detail)

    def set_status(self, state_text, detail_text):
        self.label_state.setText(state_text)
        self.label_detail.setText(detail_text)


class DashboardWidget(QWidget):
    connect_motor_requested = pyqtSignal()
    check_avp_requested = pyqtSignal()
    connect_avp_requested = pyqtSignal()
    disconnect_avp_requested = pyqtSignal()
    retry_avp_requested = pyqtSignal()
    connect_camera_requested = pyqtSignal()
    start_stream_requested = pyqtSignal()
    motor_init_requested = pyqtSignal()
    pose_init_requested = pyqtSignal()
    start_tracking_requested = pyqtSignal()
    stop_tracking_requested = pyqtSignal()
    safe_reset_requested = pyqtSignal()
    open_camera_tools_requested = pyqtSignal()
    open_motor_tools_requested = pyqtSignal()
    open_diagnostics_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.status_cards = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout()
        self.setLayout(root)

        header = QGroupBox("运行总览")
        header_layout = QVBoxLayout()
        header.setLayout(header_layout)
        self.label_title = QLabel("现场主控台")
        self.label_title.setObjectName("dashboardTitle")
        self.label_badge = QLabel("等待连接")
        self.label_badge.setObjectName("dashboardBadge")
        header_layout.addWidget(self.label_title)
        header_layout.addWidget(self.label_badge)
        root.addWidget(header)

        cards_group = QGroupBox("系统状态")
        cards_layout = QGridLayout()
        cards_group.setLayout(cards_layout)
        specs = [
            ("avp", "AVP", "头部姿态源"),
            ("camera", "相机", "视频与图像链路"),
            ("motor", "电机", "执行机构"),
            ("stream", "传输", "视频与网络输出"),
            ("tracking", "跟踪", "姿态跟踪状态"),
        ]
        for index, (key, title, subtitle) in enumerate(specs):
            card = StatusCard(title, subtitle)
            cards_layout.addWidget(card, index // 3, index % 3)
            self.status_cards[key] = card
        root.addWidget(cards_group)

        self.grp_device_flow = QGroupBox("设备连接")
        device_layout = QVBoxLayout()
        self.grp_device_flow.setLayout(device_layout)
        self.label_device_flow = QLabel("按顺序完成电机、AVP 与 ZED 相机链路准备。")
        self.label_device_flow.setWordWrap(True)
        device_layout.addWidget(self.label_device_flow)

        avp_group = QGroupBox("AVP 连接")
        avp_layout = QVBoxLayout()
        avp_group.setLayout(avp_layout)
        avp_settings = QGridLayout()
        avp_settings.addWidget(QLabel("AVP IP"), 0, 0)
        self.input_avp_ip = QLineEdit(getattr(config, "AVP_IP", ""))
        avp_settings.addWidget(self.input_avp_ip, 0, 1)
        self.chk_auto_reconnect = QCheckBox("Auto Reconnect")
        avp_settings.addWidget(self.chk_auto_reconnect, 1, 0, 1, 2)
        avp_layout.addLayout(avp_settings)

        avp_buttons = QGridLayout()
        self.btn_connect_avp = QPushButton("Connect AVP")
        self.btn_disconnect_avp = QPushButton("Disconnect AVP")
        self.btn_retry_avp = QPushButton("Retry AVP")
        self.btn_connect_avp.clicked.connect(self.connect_avp_requested.emit)
        self.btn_disconnect_avp.clicked.connect(self.disconnect_avp_requested.emit)
        self.btn_retry_avp.clicked.connect(self.retry_avp_requested.emit)
        avp_buttons.addWidget(self.btn_connect_avp, 0, 0)
        avp_buttons.addWidget(self.btn_disconnect_avp, 0, 1)
        avp_buttons.addWidget(self.btn_retry_avp, 1, 0, 1, 2)
        avp_layout.addLayout(avp_buttons)

        self.label_avp_runtime = QLabel("未连接。")
        self.label_avp_runtime.setWordWrap(True)
        self.label_avp_detail = QLabel("首次连接需手动触发。")
        self.label_avp_detail.setWordWrap(True)
        avp_layout.addWidget(self.label_avp_runtime)
        avp_layout.addWidget(self.label_avp_detail)
        device_layout.addWidget(avp_group)

        device_buttons = QGridLayout()
        device_layout.addLayout(device_buttons)

        self.btn_connect_motor = QPushButton("连接电机")
        self.btn_check_avp = QPushButton("检查 AVP")
        self.btn_connect_camera = QPushButton("连接 ZED 相机")
        self.btn_start_stream = QPushButton("开启传输")
        self.btn_connect_motor.clicked.connect(self.connect_motor_requested.emit)
        self.btn_check_avp.clicked.connect(self.check_avp_requested.emit)
        self.btn_connect_camera.clicked.connect(self.connect_camera_requested.emit)
        self.btn_start_stream.clicked.connect(self.start_stream_requested.emit)
        for index, button in enumerate(
            [
                self.btn_connect_motor,
                self.btn_check_avp,
                self.btn_connect_camera,
                self.btn_start_stream,
            ]
        ):
            button.setMinimumHeight(44)
            device_buttons.addWidget(button, index // 2, index % 2)
        root.addWidget(self.grp_device_flow)

        self.grp_init_flow = QGroupBox("初始化")
        init_layout = QVBoxLayout()
        self.grp_init_flow.setLayout(init_layout)
        self.label_init_flow = QLabel("分别完成电机就位与头姿同步，不在此阶段直接进入跟踪。")
        self.label_init_flow.setWordWrap(True)
        init_layout.addWidget(self.label_init_flow)
        init_buttons = QGridLayout()
        init_layout.addLayout(init_buttons)

        self.btn_motor_init = QPushButton("电机初始化")
        self.btn_pose_init = QPushButton("头姿初始化")
        self.btn_motor_init.clicked.connect(self.motor_init_requested.emit)
        self.btn_pose_init.clicked.connect(self.pose_init_requested.emit)
        for index, button in enumerate([self.btn_motor_init, self.btn_pose_init]):
            button.setMinimumHeight(44)
            init_buttons.addWidget(button, 0, index)
        root.addWidget(self.grp_init_flow)

        self.grp_tracking_flow = QGroupBox("跟踪控制")
        tracking_layout = QVBoxLayout()
        self.grp_tracking_flow.setLayout(tracking_layout)
        self.label_tracking_flow = QLabel("前置步骤完成后再开始跟踪，停止后可执行安全复位。")
        self.label_tracking_flow.setWordWrap(True)
        tracking_layout.addWidget(self.label_tracking_flow)
        tracking_buttons = QGridLayout()
        tracking_layout.addLayout(tracking_buttons)

        self.btn_start = QPushButton("开始跟踪")
        self.btn_stop = QPushButton("停止跟踪")
        self.btn_safe_reset = QPushButton("安全复位")
        self.btn_start.clicked.connect(self.start_tracking_requested.emit)
        self.btn_stop.clicked.connect(self.stop_tracking_requested.emit)
        self.btn_safe_reset.clicked.connect(self.safe_reset_requested.emit)
        for index, button in enumerate([self.btn_start, self.btn_stop, self.btn_safe_reset]):
            button.setMinimumHeight(44)
            tracking_buttons.addWidget(button, 0, index)
        root.addWidget(self.grp_tracking_flow)

        runtime_group = QGroupBox("运行反馈")
        runtime_layout = QVBoxLayout()
        runtime_group.setLayout(runtime_layout)
        self.label_summary = QLabel("等待系统初始化。")
        self.label_summary.setWordWrap(True)
        self.label_next_step = QLabel("下一步建议将在此显示。")
        self.label_next_step.setWordWrap(True)
        self.label_blockers = QLabel("当前无阻塞项。")
        self.label_blockers.setWordWrap(True)
        runtime_layout.addWidget(self.label_summary)
        runtime_layout.addWidget(self.label_next_step)
        runtime_layout.addWidget(self.label_blockers)
        root.addWidget(runtime_group)

        tools_group = QGroupBox("高级工具")
        tools_layout = QHBoxLayout()
        tools_group.setLayout(tools_layout)
        self.btn_open_camera = QPushButton("相机与串流")
        self.btn_open_camera.clicked.connect(self.open_camera_tools_requested.emit)
        self.btn_open_motor = QPushButton("电机与初始化")
        self.btn_open_motor.clicked.connect(self.open_motor_tools_requested.emit)
        self.btn_open_diagnostics = QPushButton("诊断与日志")
        self.btn_open_diagnostics.clicked.connect(self.open_diagnostics_requested.emit)
        tools_layout.addWidget(self.btn_open_camera)
        tools_layout.addWidget(self.btn_open_motor)
        tools_layout.addWidget(self.btn_open_diagnostics)
        root.addWidget(tools_group)
        root.addStretch()

    def update_system_snapshot(self, snapshot):
        dashboard_state = derive_dashboard_state(snapshot)
        self.status_cards["avp"].set_status(
            "姿态有效" if snapshot.pose_sample_valid else ("已连接" if snapshot.avp_connected else "未连接"),
            (
                "头部姿态输入可用。"
                if snapshot.pose_sample_valid
                else (
                    f"姿态样本无效：{snapshot.pose_sample_reason or '等待首帧'}。"
                    if snapshot.avp_connected
                    else "等待 AVP 客户端初始化。"
                )
            ),
        )
        self.status_cards["camera"].set_status(
            "在线" if snapshot.camera_connected else "离线",
            "ZED 相机链路可用。" if snapshot.camera_connected else "等待连接 ZED 相机。",
        )
        self.status_cards["motor"].set_status(
            "就绪" if snapshot.motor_ready else ("已连接" if snapshot.motor_connected else "未连接"),
            (
                "执行机构就绪。"
                if snapshot.motor_ready
                else (
                    snapshot.motor_reason or "串口已连接，但电机当前不可用。"
                    if snapshot.motor_connected
                    else "请先连接 Dynamixel 电机。"
                )
            ),
        )
        self.status_cards["stream"].set_status(
            "运行中" if snapshot.streaming else "未启动",
            "传输链路已建立。" if snapshot.streaming else "ZED 传输尚未开启。",
        )
        self.status_cards["tracking"].set_status(
            "已暂停" if snapshot.tracking_paused else ("跟踪中" if snapshot.tracking else "待机"),
            snapshot.last_warning if snapshot.last_warning else dashboard_state.summary,
        )

        self.label_badge.setText(dashboard_state.hero_label)
        self.label_summary.setText(dashboard_state.summary)
        self.label_next_step.setText(dashboard_state.next_step)
        self.label_blockers.setText(dashboard_state.blocked_reason or "当前无阻塞项。")

        self.btn_connect_motor.setEnabled(dashboard_state.connect_motor_enabled)
        self.btn_check_avp.setEnabled(dashboard_state.check_avp_enabled)
        self.btn_connect_camera.setEnabled(dashboard_state.connect_camera_enabled)
        self.btn_start_stream.setEnabled(dashboard_state.start_stream_enabled)
        self.btn_motor_init.setEnabled(dashboard_state.motor_init_enabled)
        self.btn_pose_init.setEnabled(dashboard_state.pose_init_enabled)
        self.btn_start.setEnabled(dashboard_state.start_tracking_enabled)
        self.btn_stop.setEnabled(dashboard_state.stop_tracking_enabled)
        self.btn_safe_reset.setEnabled(dashboard_state.safe_reset_enabled)

    def get_avp_settings(self):
        return {
            "ip": self.input_avp_ip.text().strip(),
            "auto_reconnect": self.chk_auto_reconnect.isChecked(),
        }

    def set_avp_settings(self, ip, auto_reconnect):
        self.input_avp_ip.setText(str(ip))
        self.chk_auto_reconnect.setChecked(bool(auto_reconnect))

    def update_avp_runtime(self, runtime):
        state = runtime.get("state", "idle")
        age = runtime.get("state_age_sec", 0.0)
        last_error = runtime.get("last_error")
        auto_reconnect = runtime.get("auto_reconnect", False)

        detail = f"状态: {state}"
        if age:
            detail += f" | 持续 {age:.1f}s"
        self.label_avp_runtime.setText(detail)

        if last_error:
            self.label_avp_detail.setText(f"最近错误: {last_error}")
        elif auto_reconnect:
            self.label_avp_detail.setText("已启用自动重连。")
        else:
            self.label_avp_detail.setText("首次连接需手动触发。")
