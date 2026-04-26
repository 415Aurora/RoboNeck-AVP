import threading
import time

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from avp_stream.streamer import VisionProStreamer
    VISION_PRO_STREAMER_IMPORT_ERROR = ""
except ImportError as exc:
    VisionProStreamer = None
    VISION_PRO_STREAMER_IMPORT_ERROR = str(exc)
    print("Warning: avp_stream not found. Only mock mode will work.")

from config import config
from src.core.controller import HeadPoseSample
from src.utils.orientation import extract_avp_head_euler


AVP_RECONNECT_RETRY_SEC = 1.0
AVP_RECOVERY_TIMEOUT_SEC = max(1.0, float(getattr(config, "AVP_TIMEOUT_SEC", 0.25)) * 4.0)


class AVPClient:
    """
    Manual-connect AVP client with optional background reconnect.
    """

    def __init__(self, ip):
        self.ip = str(ip)
        self.streamer = None
        self.running = False
        self.using_dummy_video = False
        self.frame_source = None
        self.stream_resolution = getattr(config, "STREAM_RESOLUTION", "1280x720")
        self.stream_fps = getattr(config, "STREAM_FPS", 30)
        self.stream_bitrate = 8192

        self._streamer_lock = threading.Lock()
        self._streamer_thread = None
        self._streamer_error = None
        self._streamer_import_error = VISION_PRO_STREAMER_IMPORT_ERROR
        self._connect_requested = False
        self._auto_reconnect = False
        self._stop_event = threading.Event()
        self._last_sample_timestamp = None
        self._last_head_matrix = None
        self._has_ever_received_pose = False
        self._last_pose_status = {
            "valid": False,
            "reason": "idle",
            "fresh": False,
            "last_sample_timestamp": None,
            "source_timestamp": None,
            "last_matrix_shape": None,
            "error": None,
            "state_since_monotonic": time.monotonic(),
        }
        self._connection_status = {
            "state": "idle",
            "ip": self.ip,
            "auto_reconnect": False,
            "last_error": None,
            "state_since_monotonic": time.monotonic(),
            "last_sample_timestamp": None,
            "has_ever_received_pose": False,
        }

    def connect(self, ip=None, auto_reconnect=True):
        if ip:
            self.ip = str(ip)

        self._connect_requested = True
        self._auto_reconnect = bool(auto_reconnect)
        self._stop_event.clear()

        if VisionProStreamer is None:
            self._streamer_import_error = self._streamer_import_error or "VisionProStreamer import failed."
            self._set_connection_state("import_failed", error=self._streamer_import_error)
            self._set_pose_status(
                valid=False,
                reason="streamer_import_failed",
                fresh=False,
                error=self._streamer_import_error,
            )
            self._connect_requested = False
            return False

        if self.streamer is not None:
            state = "ready" if self._has_ever_received_pose else "connected_waiting_first_sample"
            self._set_connection_state(state)
            return True

        if self._streamer_thread and self._streamer_thread.is_alive():
            self._set_connection_state("reconnecting" if self._auto_reconnect else "connecting")
            return True

        self._set_connection_state("connecting")
        self._set_pose_status(valid=False, reason="streamer_initializing", fresh=False)
        self._start_streamer_thread()
        return True

    def disconnect(self):
        self._connect_requested = False
        self._auto_reconnect = False
        self._stop_event.set()
        self._cleanup_streamer()

        worker = self._streamer_thread
        if worker and worker.is_alive() and worker is not threading.current_thread():
            worker.join(timeout=0.2)
        if self._streamer_thread is worker:
            self._streamer_thread = None

        self._set_connection_state("disconnected")
        self._set_pose_status(valid=False, reason="disconnected", fresh=False)

    def retry_now(self):
        if not self.ip:
            return False

        self._connect_requested = True
        self._stop_event.clear()
        self._cleanup_streamer()
        self._set_connection_state("reconnecting")
        self._set_pose_status(valid=False, reason="streamer_initializing", fresh=False)
        self._start_streamer_thread()
        return True

    def get_connection_status(self):
        status = dict(getattr(self, "_connection_status", {}))
        state_since = status.get("state_since_monotonic")
        status["state_age_sec"] = round(max(0.0, time.monotonic() - state_since), 6) if state_since is not None else 0.0
        return status

    def get_pose_status(self):
        status = dict(getattr(self, "_last_pose_status", {}))
        reason = status.get("reason", "idle")

        if reason in {"idle", "disconnected"}:
            pass
        elif getattr(self, "_streamer_import_error", "") and self.streamer is None:
            status["reason"] = "streamer_import_failed"
            status["error"] = getattr(self, "_streamer_import_error", "")
        elif self.streamer is None:
            if self._streamer_thread is not None and self._streamer_thread.is_alive():
                status["reason"] = "streamer_initializing"
            elif self._streamer_error is not None:
                status["reason"] = "streamer_init_failed"
                status["error"] = str(self._streamer_error)
            elif self._connect_requested:
                status["reason"] = "streamer_initializing"
            else:
                status["reason"] = status.get("reason", "idle")
        elif not getattr(self, "_has_ever_received_pose", False) and status.get("reason") in {
            "",
            "uninitialized",
            "streamer_not_ready",
            "streamer_initializing",
            "idle",
            "disconnected",
            "stream_established_waiting_first_sample",
        }:
            status["reason"] = "stream_established_waiting_first_sample"

        state_since = status.get("state_since_monotonic")
        status["state_age_sec"] = round(max(0.0, time.monotonic() - state_since), 6) if state_since is not None else 0.0
        return status

    def get_camera_imu(self):
        frame_source = getattr(self, "frame_source", None)
        if frame_source and hasattr(frame_source, "get_imu_data"):
            return frame_source.get_imu_data()
        return None

    def start_video_stream(
        self,
        frame_source=None,
        resolution=None,
        fps=None,
        bitrate=None,
        stereo=True,
        latency="Balanced",
    ):
        if not config.ENABLE_VIDEO:
            print("Video streaming disabled in config.")
            return False

        if resolution:
            self.stream_resolution = resolution
        if fps:
            self.stream_fps = fps
        if bitrate:
            self.stream_bitrate = bitrate

        self.frame_source = frame_source
        self.using_dummy_video = self.frame_source is None
        if self.frame_source is None and not getattr(config, "USE_DUMMY_VIDEO_IF_NO_CAMERA", False):
            return False

        if self.streamer is None:
            print("Error: Streamer is not initialized. Cannot configure video.")
            return False

        self.streamer.configure_video(
            device=None,
            size=self.stream_resolution,
            fps=self.stream_fps,
            stereo=stereo,
            bitrate=self.stream_bitrate,
        )
        self.streamer.register_frame_callback(self._video_callback)
        self.streamer.start_webrtc(port=9999)
        print(f"Configuring WebRTC Video: {latency} Mode...")
        print("WebRTC Stream Started on port 9999.")
        return True

    def stop_video_stream(self, close_camera=False):
        if self.streamer:
            self.streamer.cleanup()
        return True

    def restart_video_stream(
        self,
        frame_source=None,
        resolution=None,
        fps=None,
        bitrate=None,
        stereo=True,
        latency="Balanced",
    ):
        print(
            f"Restarting stream: {resolution} @ {fps}fps, {bitrate}kbps, "
            f"Stereo={stereo}, Latency={latency}"
        )
        self.stop_video_stream(close_camera=False)
        time.sleep(1.0)
        return self.start_video_stream(
            frame_source=frame_source,
            resolution=resolution,
            fps=fps,
            bitrate=bitrate,
            stereo=stereo,
            latency=latency,
        )

    def get_latest_head_pose_sample(self, now=None):
        if now is None:
            now = time.monotonic()

        if self.streamer is None:
            return self._handle_missing_streamer(now)

        try:
            data = self.streamer.get_latest()
        except Exception as exc:
            self._streamer_error = exc
            self._set_pose_status(valid=False, reason="streamer_read_failed", fresh=False, error=str(exc))
            if self._connect_requested and self._auto_reconnect:
                self._schedule_reconnect("streamer_read_failed")
            return None

        if not data:
            return self._handle_empty_payload(now)

        if "head" not in data:
            self._set_pose_status(valid=False, reason="missing_head_field", fresh=False)
            return None

        head_mat = np.asarray(data["head"])
        if head_mat.ndim == 3:
            head_mat = head_mat[0]

        if head_mat.shape != (4, 4):
            self._set_pose_status(
                valid=False,
                reason="invalid_head_shape",
                fresh=False,
                last_matrix_shape=tuple(head_mat.shape),
            )
            return None

        if not np.isfinite(head_mat).all():
            self._set_pose_status(valid=False, reason="invalid_head_values", fresh=False)
            return None

        source_timestamp = data.get("timestamp")
        sample_timestamp = now if source_timestamp is None else float(source_timestamp)
        fresh = True
        if now is not None and sample_timestamp is not None:
            fresh = (now - sample_timestamp) <= float(getattr(config, "AVP_TIMEOUT_SEC", 0.25))

        sample = HeadPoseSample(
            head_pose_matrix=head_mat,
            timestamp=sample_timestamp,
            base_imu_rpy=self.get_camera_imu(),
            raw_payload={
                **data,
                "fresh": fresh,
                "source_timestamp": source_timestamp,
            },
            fresh=fresh,
            source_timestamp=source_timestamp,
        )

        self._last_head_matrix = head_mat
        self._last_sample_timestamp = sample_timestamp
        self._has_ever_received_pose = True
        self._set_connection_state("ready")
        self._set_pose_status(
            valid=True,
            reason="" if fresh else "stale_sample",
            fresh=fresh,
            last_sample_timestamp=sample_timestamp,
            source_timestamp=source_timestamp,
            last_matrix_shape=tuple(head_mat.shape),
        )

        if (
            not fresh
            and getattr(self, "_connect_requested", False)
            and getattr(self, "_auto_reconnect", False)
            and now - sample_timestamp > AVP_RECOVERY_TIMEOUT_SEC
        ):
            self._schedule_reconnect("stale_sample")
        return sample

    def get_latest_head_pose(self):
        matrix = self.get_latest_head_pose_matrix()
        if matrix is None:
            return None

        try:
            yaw, pitch, roll = extract_avp_head_euler(matrix[:3, :3])
            return yaw, pitch, roll
        except Exception:
            return None

    def get_latest_head_pose_matrix(self):
        sample = self.get_latest_head_pose_sample()
        if sample is not None:
            return sample.head_pose_matrix
        return self._last_head_matrix

    def _video_callback(self, blank_frame):
        if self.using_dummy_video:
            res = getattr(config, "STREAM_RESOLUTION", "1280x720")
            target_w, target_h = map(int, res.split("x"))
            frame = np.zeros((target_h, target_w, 3), dtype=np.uint8)
            if cv2 is None:
                return frame

            t = time.time()
            shift = int(t * 100) % target_w
            frame[:, : target_w // 2, 2] = (np.arange(target_w // 2) + shift) % 255
            frame[:, target_w // 2 :, 0] = (np.arange(target_w // 2) + shift) % 255
            cv2.putText(frame, "TEST PATTERN - LEFT", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(
                frame,
                "TEST PATTERN - RIGHT",
                (target_w // 2 + 50, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2,
            )
            cv2.putText(frame, f"Time: {t:.2f}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            return frame

        if self.frame_source:
            ret, frame = self.frame_source.read()
            if ret:
                return frame
        return blank_frame

    def close(self):
        self.disconnect()

    def _handle_missing_streamer(self, now):
        if getattr(self, "_streamer_import_error", ""):
            self._set_pose_status(
                valid=False,
                reason="streamer_import_failed",
                fresh=False,
                error=self._streamer_import_error,
            )
            return None

        if self._streamer_thread is not None and self._streamer_thread.is_alive():
            self._set_pose_status(valid=False, reason="streamer_initializing", fresh=False)
            return None

        if self._streamer_error is not None:
            self._set_pose_status(
                valid=False,
                reason="streamer_init_failed",
                fresh=False,
                error=str(self._streamer_error),
            )
            return None

        self._set_pose_status(valid=False, reason="idle" if not self._connect_requested else "streamer_initializing", fresh=False)
        return None

    def _handle_empty_payload(self, now):
        if not getattr(self, "_has_ever_received_pose", False):
            self._set_connection_state("connected_waiting_first_sample")
            self._set_pose_status(valid=False, reason="stream_established_waiting_first_sample", fresh=False)
            status = self.get_connection_status()
            if (
                getattr(self, "_connect_requested", False)
                and getattr(self, "_auto_reconnect", False)
                and status["state_age_sec"] > AVP_RECOVERY_TIMEOUT_SEC
            ):
                self._schedule_reconnect("waiting_for_first_sample")
            return None

        last_timestamp = self._last_sample_timestamp
        if last_timestamp is None:
            self._set_pose_status(valid=False, reason="sample_missing", fresh=False)
            return None

        age_sec = max(0.0, now - last_timestamp)
        reason = "stale_sample" if age_sec > float(getattr(config, "AVP_TIMEOUT_SEC", 0.25)) else "sample_missing"
        self._set_pose_status(
            valid=False,
            reason=reason,
            fresh=False,
            last_sample_timestamp=last_timestamp,
        )
        if (
            getattr(self, "_connect_requested", False)
            and getattr(self, "_auto_reconnect", False)
            and age_sec > AVP_RECOVERY_TIMEOUT_SEC
        ):
            self._schedule_reconnect(reason)
        return None

    def _start_streamer_thread(self):
        if self._streamer_thread and self._streamer_thread.is_alive():
            return
        self._streamer_thread = threading.Thread(
            target=self._connect_streamer_worker,
            name="avp-streamer-connect",
            daemon=True,
        )
        self._streamer_thread.start()

    def _connect_streamer_worker(self):
        try:
            while self._connect_requested and not self._stop_event.is_set():
                try:
                    streamer = VisionProStreamer(ip=self.ip, record=True)
                    if self._stop_event.is_set() or not self._connect_requested:
                        if hasattr(streamer, "cleanup"):
                            streamer.cleanup()
                        return
                    with self._streamer_lock:
                        self.streamer = streamer
                    self._streamer_error = None
                    self._set_connection_state("connected_waiting_first_sample")
                    self._set_pose_status(valid=False, reason="stream_established_waiting_first_sample", fresh=False)
                    return
                except Exception as exc:
                    self._streamer_error = exc
                    if not self._auto_reconnect:
                        self._connect_requested = False
                        self._set_connection_state("connect_failed", error=str(exc))
                        self._set_pose_status(valid=False, reason="streamer_init_failed", fresh=False, error=str(exc))
                        return
                    self._set_connection_state("reconnecting", error=str(exc))
                    self._set_pose_status(valid=False, reason="streamer_initializing", fresh=False, error=str(exc))
                    if self._stop_event.wait(AVP_RECONNECT_RETRY_SEC):
                        return
        finally:
            self._streamer_thread = None

    def _schedule_reconnect(self, error_reason):
        if not self._connect_requested or not self._auto_reconnect:
            return

        self._cleanup_streamer()
        self._set_connection_state("reconnecting", error=error_reason)
        self._set_pose_status(valid=False, reason="streamer_initializing", fresh=False, error=error_reason)
        self._start_streamer_thread()

    def _cleanup_streamer(self):
        with self._streamer_lock:
            streamer = self.streamer
            self.streamer = None
        if streamer and hasattr(streamer, "cleanup"):
            try:
                streamer.cleanup()
            except Exception:
                pass

    def _set_connection_state(self, state, error=None):
        current = getattr(self, "_connection_status", {})
        now = time.monotonic()
        payload = dict(current)
        payload["state"] = state
        payload["ip"] = getattr(self, "ip", payload.get("ip", ""))
        payload["auto_reconnect"] = bool(getattr(self, "_auto_reconnect", payload.get("auto_reconnect", False)))
        payload["last_error"] = error if error is not None else payload.get("last_error")
        payload["last_sample_timestamp"] = getattr(self, "_last_sample_timestamp", payload.get("last_sample_timestamp"))
        payload["has_ever_received_pose"] = bool(getattr(self, "_has_ever_received_pose", payload.get("has_ever_received_pose", False)))
        if current.get("state") != state:
            payload["state_since_monotonic"] = now
        else:
            payload["state_since_monotonic"] = payload.get("state_since_monotonic", now)
        if error is None and state in {"idle", "connecting", "connected_waiting_first_sample", "ready", "reconnecting", "disconnected"}:
            payload["last_error"] = None
        self._connection_status = payload

    def _set_pose_status(
        self,
        valid,
        reason,
        fresh,
        last_sample_timestamp=None,
        source_timestamp=None,
        last_matrix_shape=None,
        error=None,
    ):
        current = getattr(self, "_last_pose_status", {})
        now = time.monotonic()
        payload = dict(current)
        payload["valid"] = bool(valid)
        payload["reason"] = reason
        payload["fresh"] = bool(fresh)
        payload["last_sample_timestamp"] = last_sample_timestamp
        payload["source_timestamp"] = source_timestamp
        payload["last_matrix_shape"] = last_matrix_shape
        payload["error"] = error
        if current.get("reason") != reason:
            payload["state_since_monotonic"] = now
        else:
            payload["state_since_monotonic"] = payload.get("state_since_monotonic", now)
        self._last_pose_status = payload
