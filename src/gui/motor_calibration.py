from PyQt6.QtWidgets import QGroupBox, QLabel, QVBoxLayout, QWidget


class MotorCalibrationPage(QWidget):
    def __init__(self, pose_widget, dxl_debug_widget, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        self.setLayout(layout)

        operator_group = QGroupBox("日常控制")
        operator_layout = QVBoxLayout()
        operator_group.setLayout(operator_layout)
        operator_hint = QLabel("高频操作集中在上方，包括跟踪启停、回中与基础校准。")
        operator_hint.setWordWrap(True)
        operator_layout.addWidget(operator_hint)
        operator_layout.addWidget(pose_widget)

        engineer_group = QGroupBox("高级调试")
        engineer_layout = QVBoxLayout()
        engineer_group.setLayout(engineer_layout)
        engineer_hint = QLabel("低频但高影响的调参动作放在这里，现场操作尽量不要频繁触达。")
        engineer_hint.setWordWrap(True)
        engineer_layout.addWidget(engineer_hint)
        engineer_layout.addWidget(dxl_debug_widget)

        layout.addWidget(operator_group)
        layout.addWidget(engineer_group)
