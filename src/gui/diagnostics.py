from PyQt6.QtWidgets import QGroupBox, QLabel, QTextBrowser, QVBoxLayout, QWidget


class DiagnosticsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._recent_entries = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        summary_group = QGroupBox("系统摘要")
        summary_layout = QVBoxLayout()
        summary_group.setLayout(summary_layout)
        self.label_summary = QLabel("等待状态更新。")
        self.label_summary.setWordWrap(True)
        self.label_warning = QLabel("最近告警：无")
        self.label_warning.setWordWrap(True)
        self.label_recent_action = QLabel("最近动作：无")
        self.label_recent_action.setWordWrap(True)
        summary_layout.addWidget(self.label_summary)
        summary_layout.addWidget(self.label_warning)
        summary_layout.addWidget(self.label_recent_action)
        layout.addWidget(summary_group)

        log_group = QGroupBox("事件日志")
        log_layout = QVBoxLayout()
        log_group.setLayout(log_layout)
        self.log_browser = QTextBrowser()
        log_layout.addWidget(self.log_browser)
        layout.addWidget(log_group)

    def update_system_snapshot(self, snapshot):
        self.label_summary.setText(
            "AVP={avp} | 姿态={pose} | 相机={camera} | 电机={motor} | 传输={stream} | 电机初始化={motor_init} | 头姿初始化={pose_init} | 跟踪={tracking}".format(
                avp="就绪" if snapshot.avp_connected else "等待",
                pose="有效" if snapshot.pose_sample_valid else (snapshot.pose_sample_reason or "无效"),
                camera="在线" if snapshot.camera_connected else "离线",
                motor="就绪" if snapshot.motor_ready else ("未就绪" if snapshot.motor_connected else "离线"),
                stream="运行中" if snapshot.streaming else "未启动",
                motor_init="完成" if snapshot.motor_initialized else "待执行",
                pose_init="完成" if snapshot.pose_initialized else "待执行",
                tracking="已暂停" if snapshot.tracking_paused else ("运行中" if snapshot.tracking else "待机"),
            )
        )
        self.label_warning.setText(f"最近告警：{snapshot.last_warning or '无'}")

    def add_entry(self, level, message):
        entry = f"[{level.upper()}] {message}"
        self._recent_entries.append(entry)
        self._recent_entries = self._recent_entries[-100:]
        self.label_recent_action.setText(f"最近动作：{entry}")
        self.log_browser.append(entry)
