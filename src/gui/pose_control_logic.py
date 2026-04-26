def format_pose_text(pose):
    return f"Yaw {pose['yaw']:.1f} deg | Pitch {pose['pitch']:.1f} deg"


def build_tracking_start_display(current_pose, previous_pose, path, has_saved_record):
    source_prefix = "Saved record" if has_saved_record else "Config fallback"
    return {
        "current_text": format_pose_text(current_pose),
        "previous_text": format_pose_text(previous_pose),
        "source_text": f"{source_prefix}: {path}",
    }


def build_pose_control_view_state(motors_connected, is_tracking, manual_adjust_active):
    if not motors_connected:
        status_text = "Disconnected"
        step_message = "Connect motors before manual adjustment. Manual angle input can still be saved."
    elif manual_adjust_active:
        status_text = "Manual Adjust"
        step_message = "Torque released. Adjust the neck by hand, then click 'Read Motor Pose & Save'."
    elif is_tracking:
        status_text = "Tracking"
        step_message = "Tracking head pose in real time."
    else:
        status_text = "Idle"
        step_message = "Review the saved home position, then calibrate or start tracking."

    return {
        "status_text": status_text,
        "step_message": step_message,
        "release_enabled": motors_connected and not manual_adjust_active,
        "capture_enabled": motors_connected and manual_adjust_active,
        "tracking_enabled": not manual_adjust_active,
    }


def resolve_base_imu(camera_controller, imu_enabled):
    if not imu_enabled or camera_controller is None:
        return None
    return camera_controller.get_imu_data()
