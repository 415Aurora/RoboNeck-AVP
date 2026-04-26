import sys
import os

# Ensure the project root is in sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, root_dir)

# Add VisionProTeleop to path (assuming it's a sibling of RobotNeck-AVP)
# Structure: /Projects/Robot/RoboNeck-AVP/RobotNeck-AVP
#            /Projects/Robot/RoboNeck-AVP/VisionProTeleop
sibling_dir = os.path.dirname(root_dir)
vision_pro_dir = os.path.join(sibling_dir, "VisionProTeleop")
if os.path.exists(vision_pro_dir):
    sys.path.insert(0, vision_pro_dir)


from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
