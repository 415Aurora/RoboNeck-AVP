from dataclasses import dataclass


@dataclass(frozen=True)
class SystemSnapshot:
    avp_connected: bool
    camera_connected: bool
    motor_connected: bool
    motor_ready: bool
    motor_reason: str
    streaming: bool
    tracking: bool
    tracking_paused: bool
    motor_initialized: bool
    pose_initialized: bool
    pose_sample_valid: bool = False
    pose_sample_reason: str = ""
    pose_sample_fresh: bool = False
    last_warning: str = ""


@dataclass(frozen=True)
class DashboardState:
    status_tone: str
    hero_label: str
    next_step: str
    summary: str
    blocked_reason: str
    connect_motor_enabled: bool
    check_avp_enabled: bool
    connect_camera_enabled: bool
    start_stream_enabled: bool
    motor_init_enabled: bool
    pose_init_enabled: bool
    start_tracking_enabled: bool
    stop_tracking_enabled: bool
    safe_reset_enabled: bool


def derive_dashboard_state(snapshot: SystemSnapshot) -> DashboardState:
    base = {
        "connect_motor_enabled": not snapshot.motor_connected,
        "check_avp_enabled": True,
        "connect_camera_enabled": bool(snapshot.avp_connected and not snapshot.camera_connected),
        "start_stream_enabled": False,
        "motor_init_enabled": False,
        "pose_init_enabled": False,
        "start_tracking_enabled": False,
        "stop_tracking_enabled": bool(snapshot.tracking),
        "safe_reset_enabled": bool(snapshot.motor_connected and snapshot.motor_ready),
    }

    if snapshot.tracking_paused:
        reason = snapshot.pose_sample_reason or "waiting_for_valid_pose"
        return DashboardState(
            status_tone="warning",
            hero_label="已暂停",
            next_step="跟踪已暂停，等待 AVP 姿态恢复后自动继续",
            summary="跟踪会话仍保持激活，当前维持上一帧电机命令。",
            blocked_reason=f"暂停原因：{reason}",
            **{
                **base,
                "connect_motor_enabled": False,
                "check_avp_enabled": False,
                "connect_camera_enabled": False,
                "start_stream_enabled": False,
                "motor_init_enabled": False,
                "pose_init_enabled": False,
                "start_tracking_enabled": False,
                "stop_tracking_enabled": True,
            },
        )

    if snapshot.tracking:
        return DashboardState(
            status_tone="active",
            hero_label="跟踪中",
            next_step="跟踪运行中，可停止跟踪或安全复位",
            summary="当前正在执行头姿跟踪。",
            blocked_reason="",
            **{
                **base,
                "connect_motor_enabled": False,
                "check_avp_enabled": False,
                "connect_camera_enabled": False,
                "start_stream_enabled": False,
                "motor_init_enabled": False,
                "pose_init_enabled": False,
                "start_tracking_enabled": False,
                "stop_tracking_enabled": True,
            },
        )

    if snapshot.motor_connected and not snapshot.motor_ready:
        reason = snapshot.motor_reason or "电机未通过就绪检查。"
        return DashboardState(
            status_tone="warning",
            hero_label="电机未就绪",
            next_step="下一步：检查电机连接",
            summary="串口已连接，但当前无法安全控制电机。",
            blocked_reason=reason,
            **{
                **base,
                "connect_motor_enabled": False,
                "safe_reset_enabled": False,
            },
        )

    if not snapshot.motor_connected:
        return DashboardState(
            status_tone="warning",
            hero_label="等待电机",
            next_step="下一步：连接电机",
            summary="执行机构未连接，主流程停在设备连接阶段。",
            blocked_reason="电机未连接，后续初始化和跟踪动作均不可用。",
            **base,
        )

    if not snapshot.avp_connected:
        return DashboardState(
            status_tone="warning",
            hero_label="等待 AVP",
            next_step="下一步：检查 AVP",
            summary="AVP 客户端尚未就绪。",
            blocked_reason="当前没有可用的头部姿态源。",
            **{
                **base,
                "connect_motor_enabled": False,
            },
        )

    if not snapshot.pose_sample_valid:
        reason = snapshot.pose_sample_reason or "等待首帧"
        return DashboardState(
            status_tone="warning",
            hero_label="AVP 姿态异常",
            next_step="下一步：检查 AVP",
            summary="AVP 已连接，但当前没有可用的头部姿态样本。",
            blocked_reason=f"头部姿态样本无效：{reason}",
            **{
                **base,
                "connect_motor_enabled": False,
            },
        )

    if not snapshot.camera_connected:
        return DashboardState(
            status_tone="warning",
            hero_label="等待 ZED",
            next_step="下一步：连接 ZED 相机",
            summary="AVP 已就绪，等待相机链路建立。",
            blocked_reason="ZED 相机未连接，无法进入后续传输与初始化流程。",
            **{
                **base,
                "connect_motor_enabled": False,
                "connect_camera_enabled": True,
            },
        )

    if not snapshot.streaming:
        return DashboardState(
            status_tone="warning",
            hero_label="等待传输",
            next_step="下一步：开启传输",
            summary="ZED 相机已连接，下一步需要开启传输。",
            blocked_reason="传输未启动，主控台按现场流程暂停在此。",
            **{
                **base,
                "connect_motor_enabled": False,
                "connect_camera_enabled": False,
                "start_stream_enabled": True,
            },
        )

    if not snapshot.motor_initialized:
        return DashboardState(
            status_tone="warning",
            hero_label="等待电机初始化",
            next_step="下一步：电机初始化",
            summary="设备连接已完成，等待机器人回到追踪初始位。",
            blocked_reason="尚未执行电机初始化。",
            **{
                **base,
                "connect_motor_enabled": False,
                "connect_camera_enabled": False,
                "motor_init_enabled": True,
            },
        )

    if not snapshot.pose_initialized:
        pose_reason = snapshot.pose_sample_reason or "等待有效姿态样本"
        return DashboardState(
            status_tone="warning",
            hero_label="等待头姿初始化",
            next_step="下一步：头姿初始化",
            summary="电机已到位，等待捕获当前头姿并建立同步。",
            blocked_reason=f"头姿初始化尚未完成：{pose_reason}",
            **{
                **base,
                "connect_motor_enabled": False,
                "connect_camera_enabled": False,
                "pose_init_enabled": bool(snapshot.pose_sample_valid),
            },
        )

    return DashboardState(
        status_tone="ready",
        hero_label="系统就绪",
        next_step="下一步：开始跟踪",
        summary="设备连接、初始化与传输均已完成。",
        blocked_reason="",
        **{
            **base,
            "connect_motor_enabled": False,
            "connect_camera_enabled": False,
            "start_tracking_enabled": True,
        },
    )
