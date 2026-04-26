from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QVBoxLayout, QWidget


class CameraStreamPage(QWidget):
    def __init__(self, camera_widget, teleop_widget, parent=None):
        super().__init__(parent)
        root = QHBoxLayout()
        self.setLayout(root)

        stream_group = QGroupBox("ZED 传输画面")
        stream_group_layout = QVBoxLayout()
        stream_group.setLayout(stream_group_layout)
        stream_group_layout.addWidget(teleop_widget)

        camera_group = QGroupBox("相机参数")
        camera_group_layout = QVBoxLayout()
        camera_group.setLayout(camera_group_layout)
        camera_group_layout.addWidget(camera_widget)

        left = QVBoxLayout()
        left.addWidget(stream_group)
        left.addStretch()

        right = QVBoxLayout()
        right.addWidget(camera_group)
        right.addStretch()

        root.addLayout(left, 5)
        root.addLayout(right, 2)
