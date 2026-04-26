from dataclasses import dataclass
import importlib
import os
import sys

from config import config


@dataclass
class RuntimeCheck:
    name: str
    ok: bool
    required: bool
    message: str
    error: str = ""


def _probe_module(module_name):
    if module_name.startswith("avp_stream"):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sibling = os.path.join(os.path.dirname(project_root), "VisionProTeleop")
        if os.path.isdir(sibling) and sibling not in sys.path:
            sys.path.insert(0, sibling)
    try:
        importlib.import_module(module_name)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _normalize_dependency_probe(value):
    if isinstance(value, tuple) and len(value) == 2:
        return bool(value[0]), str(value[1] or "")
    if isinstance(value, dict):
        return bool(value.get("ok", False)), str(value.get("error", "") or "")
    return bool(value), ""


def gather_runtime_checks(
    mock_avp,
    mock_motors,
    enable_video,
    use_zed_sdk,
    dynamixel_port,
    dependency_status=None,
    path_exists=os.path.exists,
):
    dependency_status = dict(dependency_status or {})

    def dependency_probe(module_name):
        if module_name in dependency_status:
            return _normalize_dependency_probe(dependency_status[module_name])
        return _probe_module(module_name)

    def dependency_message(default_message, error):
        if not error:
            return default_message
        return f"{default_message} Details: {error}"

    avp_ok, avp_error = dependency_probe("avp_stream")
    dynamixel_ok, dynamixel_error = dependency_probe("dynamixel_sdk")
    cv2_ok, cv2_error = dependency_probe("cv2")
    zed_ok, zed_error = dependency_probe("pyzed.sl")

    checks = [
        RuntimeCheck(
            name="avp_stream",
            ok=avp_ok,
            required=not mock_avp,
            message=dependency_message("Install avp_stream before running with a real Vision Pro.", avp_error),
            error=avp_error,
        ),
        RuntimeCheck(
            name="dynamixel_sdk",
            ok=dynamixel_ok,
            required=not mock_motors,
            message=dependency_message("Install dynamixel_sdk before running with real motors.", dynamixel_error),
            error=dynamixel_error,
        ),
        RuntimeCheck(
            name="cv2",
            ok=cv2_ok,
            required=enable_video,
            message=dependency_message("Install OpenCV before enabling video streaming.", cv2_error),
            error=cv2_error,
        ),
        RuntimeCheck(
            name="pyzed.sl",
            ok=zed_ok,
            required=enable_video and use_zed_sdk,
            message=dependency_message("Install the ZED SDK Python bindings or disable USE_ZED_SDK.", zed_error),
            error=zed_error,
        ),
        RuntimeCheck(
            name="dynamixel_port",
            ok=bool(dynamixel_port) and path_exists(dynamixel_port),
            required=not mock_motors,
            message="Configured Dynamixel port was not found on this machine.",
        ),
    ]
    return checks


def gather_runtime_checks_from_config(config_module=config):
    return gather_runtime_checks(
        mock_avp=config_module.MOCK_AVP,
        mock_motors=config_module.MOCK_MOTORS,
        enable_video=getattr(config_module, "ENABLE_VIDEO", False),
        use_zed_sdk=getattr(config_module, "USE_ZED_SDK", False),
        dynamixel_port=getattr(config_module, "DYNAMIXEL_PORT", ""),
    )


def format_runtime_checks(checks):
    lines = []
    for check in checks:
        if check.ok:
            state = "OK"
            message = "available"
        elif check.required:
            state = "ERROR"
            message = check.message
        else:
            state = "WARN"
            message = check.message
        requirement = "required" if check.required else "optional"
        lines.append(f"[Preflight] {state} {check.name} ({requirement}) - {message}")
    return "\n".join(lines)


def validate_runtime_checks(checks):
    blocking = [check for check in checks if check.required and not check.ok]
    if blocking:
        detail = "\n".join(f"- {check.name}: {check.message}" for check in blocking)
        raise RuntimeError(f"Runtime preflight failed:\n{detail}")
    return checks


def ensure_runtime_ready(config_module=config):
    checks = gather_runtime_checks_from_config(config_module=config_module)
    return validate_runtime_checks(checks)
