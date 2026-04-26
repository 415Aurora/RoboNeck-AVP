import json
import os


class MechanicalCenterCalibration:
    def __init__(self, path, default_yaw_center, default_pitch_center):
        self.path = path
        self.default = {
            "yaw_center_step": int(default_yaw_center),
            "pitch_center_step": int(default_pitch_center),
        }

    def load(self):
        if not os.path.exists(self.path):
            return dict(self.default)

        with open(self.path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return dict(data.get("current", self.default))

    def save(self, yaw_center_step, pitch_center_step):
        current = self.load()
        payload = {
            "current": {
                "yaw_center_step": int(yaw_center_step),
                "pitch_center_step": int(pitch_center_step),
            },
            "previous": current,
        }
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        return dict(payload["current"])

    def rollback(self):
        if not os.path.exists(self.path):
            return dict(self.default)

        with open(self.path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        previous = dict(data.get("previous", self.default))
        payload = {
            "current": previous,
            "previous": dict(data.get("current", self.default)),
        }
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        return previous


class TrackingStartPoseCalibration:
    def __init__(self, path, default_yaw_step, default_pitch_step):
        self.path = path
        self.default = {
            "yaw_start_step": int(default_yaw_step),
            "pitch_start_step": int(default_pitch_step),
        }

    def load(self):
        if not os.path.exists(self.path):
            return dict(self.default)

        with open(self.path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return dict(data.get("current", self.default))

    def save(self, yaw_start_step, pitch_start_step):
        current = self.load()
        payload = {
            "current": {
                "yaw_start_step": int(yaw_start_step),
                "pitch_start_step": int(pitch_start_step),
            },
            "previous": current,
        }
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        return dict(payload["current"])

    def rollback(self):
        if not os.path.exists(self.path):
            return dict(self.default)

        with open(self.path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        previous = dict(data.get("previous", self.default))
        payload = {
            "current": previous,
            "previous": dict(data.get("current", self.default)),
        }
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        return previous


class MotorLimitCalibration:
    def __init__(self, path, default_limits):
        self.path = path
        self.default = {
            "yaw_min_step": int(default_limits["yaw_min_step"]),
            "yaw_max_step": int(default_limits["yaw_max_step"]),
            "pitch_min_step": int(default_limits["pitch_min_step"]),
            "pitch_max_step": int(default_limits["pitch_max_step"]),
        }

    def load(self):
        if not os.path.exists(self.path):
            return dict(self.default)

        with open(self.path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return dict(data.get("current", self.default))

    def save(self, yaw_min_step, yaw_max_step, pitch_min_step, pitch_max_step):
        current = self.load()
        payload = {
            "current": {
                "yaw_min_step": int(yaw_min_step),
                "yaw_max_step": int(yaw_max_step),
                "pitch_min_step": int(pitch_min_step),
                "pitch_max_step": int(pitch_max_step),
            },
            "previous": current,
        }
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        return dict(payload["current"])

    def rollback(self):
        if not os.path.exists(self.path):
            return dict(self.default)

        with open(self.path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        previous = dict(data.get("previous", self.default))
        payload = {
            "current": previous,
            "previous": dict(data.get("current", self.default)),
        }
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        return previous


class AVPConnectionCalibration:
    def __init__(self, path, default_ip, default_auto_reconnect=False):
        self.path = path
        self.default = {
            "ip": str(default_ip),
            "auto_reconnect": bool(default_auto_reconnect),
        }

    def load(self):
        if not os.path.exists(self.path):
            return dict(self.default)

        with open(self.path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        current = dict(data.get("current", self.default))
        current["ip"] = str(current.get("ip", self.default["ip"]))
        current["auto_reconnect"] = bool(current.get("auto_reconnect", self.default["auto_reconnect"]))
        return current

    def save(self, ip, auto_reconnect):
        current = self.load()
        payload = {
            "current": {
                "ip": str(ip),
                "auto_reconnect": bool(auto_reconnect),
            },
            "previous": current,
        }
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        return dict(payload["current"])

    def rollback(self):
        if not os.path.exists(self.path):
            return dict(self.default)

        with open(self.path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        previous = dict(data.get("previous", self.default))
        payload = {
            "current": previous,
            "previous": dict(data.get("current", self.default)),
        }
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        return previous
