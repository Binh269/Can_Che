"""
GPIO trigger -> capture image -> publish via MQTT.

Pin mapping:
- GPIO 22: input signal trigger
- GPIO 19: internet OK indicator
- GPIO 26: MQTT publish OK indicator

Phan MQTT da sua:
- Moi payload co them:
    + tt: so thu tu, tu tang, reset moi ngay
    + status: false
- Payload gui thanh cong len MQTT broker se duoc giu trong RAM.
- Ben nhan phan hoi ve MQTT_ACK_TOPIC:
    + {"tt": 12, "status": true}  -> xoa payload tt=12 khoi RAM va xoa file that bai neu co
    + {"tt": 12, "status": false} -> gui lai payload tt=12 trong thu muc ThatBai
- Neu publish len broker that bai -> luu payload vao thu muc ThatBai.
- Neu da publish len broker nhung sau ACK_TIMEOUT_SEC van chua co status true -> luu vao ThatBai.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import socket
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import paho.mqtt.client as mqtt
import requests
from gpiozero import DigitalInputDevice, OutputDevice

try:
    from paho.mqtt.client import CallbackAPIVersion
except Exception:  # paho-mqtt ban cu khong co CallbackAPIVersion
    CallbackAPIVersion = None


# ─── Cấu hình ─────────────────────────────────────────────────────────────────

BUTTON_PIN       = int(os.environ.get("BUTTON_PIN",       "22"))
INTERNET_LED_PIN = int(os.environ.get("INTERNET_LED_PIN", "19"))
MQTT_LED_PIN     = int(os.environ.get("MQTT_LED_PIN",     "26"))

# Pin HIGH liên tục bao nhiêu ms thì coi là nhấn
HIGH_STABLE_MS = int(os.environ.get("HIGH_STABLE_MS", "50"))
# Sau khi trigger, nghỉ bao nhiêu giây rồi mới check lại
COOLDOWN_SEC   = float(os.environ.get("COOLDOWN_SEC",  "0.0"))
# Poll mỗi bao nhiêu ms
POLL_MS        = int(os.environ.get("POLL_MS", "10"))

FRAME_API_URL      = os.environ.get("FRAME_API_URL",      "http://127.0.0.1:5000/api/frame")
FRAME_API_TIMEOUT  = float(os.environ.get("FRAME_API_TIMEOUT", "5.0"))
FRAME_API_BEARER   = os.environ.get("FRAME_API_BEARER",   "")
FRAME_API_USERNAME = os.environ.get("FRAME_API_USERNAME", "admin")
FRAME_API_PASSWORD = os.environ.get("FRAME_API_PASSWORD", "pass")
FRAME_API_HEADERS  = os.environ.get("FRAME_API_HEADERS",  "")

JPEG_QUALITY = int(os.environ.get("JPEG_QUALITY", "80"))

INTERNET_PROBE_HOST     = os.environ.get("INTERNET_PROBE_HOST",    "1.1.1.1")
INTERNET_PROBE_PORT     = int(os.environ.get("INTERNET_PROBE_PORT",    "53"))
INTERNET_PROBE_TIMEOUT  = float(os.environ.get("INTERNET_PROBE_TIMEOUT", "2.0"))
INTERNET_CHECK_INTERVAL = float(os.environ.get("INTERNET_CHECK_INTERVAL", "3.0"))

MQTT_HOST            = os.environ.get("MQTT_HOST",      "127.0.0.1")
MQTT_PORT            = int(os.environ.get("MQTT_PORT",  "1883"))
MQTT_TOPIC           = os.environ.get("MQTT_TOPIC",     "can/camera/image")
# Topic ben nhan ban ve status true/false. Co the doi bang bien moi truong MQTT_ACK_TOPIC.
MQTT_ACK_TOPIC       = os.environ.get("MQTT_ACK_TOPIC", f"{MQTT_TOPIC}/ack")
MQTT_CLIENT_ID       = os.environ.get("MQTT_CLIENT_ID", "pi-camera-uploader")
MQTT_USERNAME        = os.environ.get("MQTT_USERNAME",  "")
MQTT_PASSWORD        = os.environ.get("MQTT_PASSWORD",  "")
MQTT_KEEPALIVE       = int(os.environ.get("MQTT_KEEPALIVE",        "60"))
MQTT_QOS             = max(1, min(2, int(os.environ.get("MQTT_QOS", "1"))))
MQTT_PUBLISH_TIMEOUT = float(os.environ.get("MQTT_PUBLISH_TIMEOUT", "10.0"))
MQTT_PUBLISH_RETRIES = int(os.environ.get("MQTT_PUBLISH_RETRIES",   "3"))
MQTT_RETRY_DELAY     = float(os.environ.get("MQTT_RETRY_DELAY",     "1.0"))
MQTT_CONNECT_TIMEOUT = float(os.environ.get("MQTT_CONNECT_TIMEOUT", "8.0"))

FAILED_DIR              = Path(os.environ.get("FAILED_DIR", "ThatBai"))
ACK_TIMEOUT_SEC         = float(os.environ.get("ACK_TIMEOUT_SEC", "60.0"))
PENDING_CHECK_INTERVAL  = float(os.environ.get("PENDING_CHECK_INTERVAL", "1.0"))
SEQUENCE_STATE_FILE     = Path(os.environ.get("SEQUENCE_STATE_FILE", ".mqtt_sequence_state.json"))

CAN_ID        = os.environ.get("CAN_ID",        "CAN-001")
WEIGHT_STATUS = os.environ.get("WEIGHT_STATUS", "0")
VIETNAM_TZ    = timezone(timedelta(hours=7))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

POLL_SEC = POLL_MS / 1000.0


# ─── Internet ─────────────────────────────────────────────────────────────────

def internet_available() -> bool:
    try:
        with socket.create_connection(
            (INTERNET_PROBE_HOST, INTERNET_PROBE_PORT),
            timeout=INTERNET_PROBE_TIMEOUT,
        ):
            return True
    except OSError:
        return False


# ─── Số thứ tự reset mỗi ngày ─────────────────────────────────────────────────

_sequence_lock = threading.Lock()


def _today_key() -> str:
    return datetime.now(VIETNAM_TZ).strftime("%Y-%m-%d")


def _read_sequence_state() -> dict[str, Any]:
    try:
        if SEQUENCE_STATE_FILE.exists():
            with SEQUENCE_STATE_FILE.open("r", encoding="utf-8") as fp:
                data = json.load(fp)
            if isinstance(data, dict):
                return data
    except Exception as exc:
        logger.warning("Khong doc duoc file sequence state: %s", exc)
    return {}


def _write_sequence_state(data: dict[str, Any]) -> None:
    try:
        temp = SEQUENCE_STATE_FILE.with_suffix(".tmp")
        with temp.open("w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, separators=(",", ":"))
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(temp, SEQUENCE_STATE_FILE)
    except Exception as exc:
        logger.warning("Khong ghi duoc file sequence state: %s", exc)


def next_tt() -> int:
    """Lay so thu tu moi. Sang ngay moi tu reset ve 1."""
    with _sequence_lock:
        today = _today_key()
        data = _read_sequence_state()
        if data.get("date") != today:
            value = 1
        else:
            try:
                value = int(data.get("last_tt", 0)) + 1
            except Exception:
                value = 1
        _write_sequence_state({"date": today, "last_tt": value})
        return value


def _safe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


# ─── Lấy frame từ API ─────────────────────────────────────────────────────────

def fetch_frame_from_api():
    headers: dict = {}
    auth = None
    if FRAME_API_BEARER:
        headers["Authorization"] = f"Bearer {FRAME_API_BEARER}"
    if FRAME_API_HEADERS:
        try:
            extra = json.loads(FRAME_API_HEADERS)
            if isinstance(extra, dict):
                headers.update(extra)
        except Exception:
            logger.warning("FRAME_API_HEADERS khong phai JSON hop le, bo qua")
    if FRAME_API_USERNAME and FRAME_API_PASSWORD:
        auth = (FRAME_API_USERNAME, FRAME_API_PASSWORD)

    def _fetch_url(url: str) -> bytes:
        r = requests.get(url, timeout=FRAME_API_TIMEOUT, headers=headers or None, auth=auth)
        r.raise_for_status()
        if "image" not in r.headers.get("Content-Type", ""):
            raise RuntimeError(f"URL tra ve khong phai anh: {r.headers.get('Content-Type')}")
        return r.content

    def _extract_image_from_json(obj) -> bytes | None:
        for key in ["image", "image_base64", "frame", "frame_base64",
                    "image_url", "frame_url", "url", "data"]:
            if not isinstance(obj, dict) or key not in obj:
                continue
            v = obj[key]
            if v is None:
                continue
            if isinstance(v, str):
                s = v.strip()
                if s.startswith("data:") and ";base64," in s:
                    return base64.b64decode(s.split(";base64,", 1)[1])
                if s.startswith("http://") or s.startswith("https://"):
                    return _fetch_url(s)
                if len(s) > 100:
                    try:
                        return base64.b64decode(s)
                    except Exception:
                        pass
            if isinstance(v, dict):
                for sub in ("url", "image_url", "data", "base64"):
                    sv = v.get(sub)
                    if isinstance(sv, str) and len(sv) > 10:
                        if sv.startswith("http"):
                            return _fetch_url(sv)
                        try:
                            return base64.b64decode(sv)
                        except Exception:
                            pass
        return None

    resp = requests.get(
        FRAME_API_URL, timeout=FRAME_API_TIMEOUT,
        headers=headers or None, auth=auth,
    )
    resp.raise_for_status()
    ct = resp.headers.get("Content-Type", "")
    if "image" in ct:
        return resp.content, -1
    if "json" in ct or resp.text.lstrip().startswith("{"):
        img = _extract_image_from_json(resp.json())
        if img is not None:
            return img, -1
        raise RuntimeError("API tra ve JSON nhung khong co du lieu anh")
    raise RuntimeError(f"Content-type khong hop le: {ct}")


def ensure_jpeg(image_bytes: bytes) -> bytes:
    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return image_bytes
        ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
        return buf.tobytes() if ok else image_bytes
    except Exception:
        return image_bytes


# ─── Payload ──────────────────────────────────────────────────────────────────

def build_image_payload(jpeg_bytes: bytes, camera_index: int = -1) -> dict:
    payload = {
        "message_id":  str(uuid.uuid4()),
        "tt":          next_tt(),
        "status":      False,
        "can":         CAN_ID,
        "trong_luong": WEIGHT_STATUS,
        "thoi_gian":   datetime.now(VIETNAM_TZ).isoformat(timespec="seconds"),
        "img":         base64.b64encode(jpeg_bytes).decode("ascii"),
    }
    if camera_index >= 0:
        payload["camera_index"] = camera_index
    return payload


# ─── Lưu / đọc payload thất bại ──────────────────────────────────────────────

def _failed_file_name(payload: dict) -> str:
    ts = datetime.now(VIETNAM_TZ).strftime("%Y%m%d_%H%M%S")
    tt = payload.get("tt", "unknown")
    msg_id = str(payload.get("message_id", uuid.uuid4()))
    return f"tt{tt}_{ts}_{msg_id}.json"


def save_failed_payload(payload: dict) -> Path:
    FAILED_DIR.mkdir(parents=True, exist_ok=True)
    target = FAILED_DIR / _failed_file_name(payload)
    temp = target.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, separators=(",", ":"))
        fp.flush()
        os.fsync(fp.fileno())
    os.replace(temp, target)
    return target


def find_failed_payload_files_by_tt(tt: int) -> list[Path]:
    if not FAILED_DIR.exists():
        return []
    return sorted(FAILED_DIR.glob(f"tt{tt}_*.json"))


def delete_failed_payload_files_by_tt(tt: int) -> int:
    count = 0
    for path in find_failed_payload_files_by_tt(tt):
        try:
            path.unlink(missing_ok=True)
            count += 1
        except Exception as exc:
            logger.warning("Khong xoa duoc %s: %s", path, exc)
    return count


def read_failed_payload_by_tt(tt: int) -> tuple[Path, dict] | None:
    for path in find_failed_payload_files_by_tt(tt):
        try:
            with path.open("r", encoding="utf-8") as fp:
                payload = json.load(fp)
            if isinstance(payload, dict) and "img" in payload:
                return path, payload
            logger.warning("File that bai khong hop le: %s", path)
        except Exception as exc:
            logger.warning("Khong doc duoc %s: %s", path, exc)
    return None


# ─── RAM pending: payload da publish, dang cho status true ───────────────────

_pending_lock = threading.Lock()
_pending_payloads: dict[int, dict[str, Any]] = {}


def remember_pending_payload(payload: dict) -> None:
    tt = _safe_int(payload.get("tt"))
    if tt is None:
        logger.warning("Payload khong co tt, khong dua vao RAM pending")
        return
    with _pending_lock:
        _pending_payloads[tt] = {
            "payload": dict(payload),
            "published_at": time.monotonic(),
        }
    logger.info("Da luu payload tt=%s vao RAM, cho ACK %.0fs", tt, ACK_TIMEOUT_SEC)


def pop_pending_payload(tt: int) -> dict | None:
    with _pending_lock:
        item = _pending_payloads.pop(tt, None)
    if isinstance(item, dict) and isinstance(item.get("payload"), dict):
        return item["payload"]
    return None


def get_pending_payload(tt: int) -> dict | None:
    with _pending_lock:
        item = _pending_payloads.get(tt)
        if isinstance(item, dict) and isinstance(item.get("payload"), dict):
            return dict(item["payload"])
    return None


def pending_timeout_loop(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        expired: list[dict] = []
        now = time.monotonic()
        with _pending_lock:
            for tt, item in list(_pending_payloads.items()):
                try:
                    age = now - float(item.get("published_at", now))
                except Exception:
                    age = ACK_TIMEOUT_SEC + 1
                if age >= ACK_TIMEOUT_SEC:
                    payload = item.get("payload")
                    if isinstance(payload, dict):
                        expired.append(payload)
                    _pending_payloads.pop(tt, None)

        for payload in expired:
            try:
                p = save_failed_payload(payload)
                logger.error(
                    "Qua %.0fs chua nhan status:true, luu tt=%s vao %s",
                    ACK_TIMEOUT_SEC, payload.get("tt"), p,
                )
            except Exception as exc:
                logger.exception("Khong luu duoc payload het timeout: %s", exc)

        stop_event.wait(PENDING_CHECK_INTERVAL)


# ─── MQTT manager: publish + subscribe ACK ───────────────────────────────────

class MqttManager:
    def __init__(self) -> None:
        self.connected_event = threading.Event()
        self.client = self._create_client()
        if MQTT_USERNAME:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        try:
            self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        except Exception:
            pass

    @staticmethod
    def _create_client():
        if CallbackAPIVersion is not None:
            try:
                return mqtt.Client(
                    callback_api_version=CallbackAPIVersion.VERSION1,
                    client_id=MQTT_CLIENT_ID,
                    protocol=mqtt.MQTTv311,
                )
            except TypeError:
                pass
        return mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=mqtt.MQTTv311)

    def start(self) -> None:
        logger.info(
            "Ket noi MQTT %s:%s | publish=%s | ack=%s",
            MQTT_HOST, MQTT_PORT, MQTT_TOPIC, MQTT_ACK_TOPIC,
        )
        try:
            self.client.connect_async(MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE)
            self.client.loop_start()
        except Exception as exc:
            logger.warning("Khong khoi dong duoc MQTT client: %s", exc)

    def stop(self) -> None:
        try:
            self.client.loop_stop()
        except Exception:
            pass
        try:
            self.client.disconnect()
        except Exception:
            pass
        self.connected_event.clear()

    def _on_connect(self, client, userdata, flags, rc, *extra) -> None:
        try:
            code = int(rc)
        except Exception:
            code = 0 if str(rc).lower() == "success" else -1
        if code == 0:
            self.connected_event.set()
            logger.info("MQTT da ket noi, subscribe ACK topic=%s", MQTT_ACK_TOPIC)
            try:
                client.subscribe(MQTT_ACK_TOPIC, qos=MQTT_QOS)
            except Exception as exc:
                logger.warning("Subscribe ACK topic that bai: %s", exc)
        else:
            self.connected_event.clear()
            logger.warning("MQTT ket noi that bai rc=%s", rc)

    def _on_disconnect(self, client, userdata, rc, *extra) -> None:
        self.connected_event.clear()
        logger.warning("MQTT mat ket noi rc=%s", rc)

    def _on_message(self, client, userdata, msg) -> None:
        try:
            data = json.loads(msg.payload.decode("utf-8", errors="replace"))
        except Exception as exc:
            logger.warning("ACK khong phai JSON hop le: %s", exc)
            return

        if not isinstance(data, dict):
            logger.warning("ACK khong phai object JSON: %r", data)
            return

        tt = _safe_int(data.get("tt"))
        status = data.get("status")
        if tt is None or not isinstance(status, bool):
            logger.warning("ACK thieu tt/status bool: %s", data)
            return

        if status is True:
            pop_pending_payload(tt)
            deleted = delete_failed_payload_files_by_tt(tt)
            logger.info("Nhan status:true tt=%s -> xoa RAM, xoa %d file ThatBai", tt, deleted)
        else:
            logger.warning("Nhan status:false tt=%s -> thu gui lai file ThatBai", tt)
            threading.Thread(
                target=self.resend_failed_payload_by_tt,
                name=f"resend-tt-{tt}",
                args=(tt,),
                daemon=True,
            ).start()

    def publish_payload(self, payload: dict, remember_pending: bool = True) -> bool:
        for attempt in range(1, MQTT_PUBLISH_RETRIES + 1):
            if self._publish_once(payload):
                if remember_pending:
                    remember_pending_payload(payload)
                return True
            if attempt < MQTT_PUBLISH_RETRIES:
                logger.warning("Thu lai MQTT lan %s/%s", attempt + 1, MQTT_PUBLISH_RETRIES)
                time.sleep(MQTT_RETRY_DELAY)
        return False

    def _publish_once(self, payload: dict) -> bool:
        try:
            if not self.connected_event.wait(timeout=MQTT_CONNECT_TIMEOUT):
                logger.warning("MQTT chua ket noi sau %.1fs", MQTT_CONNECT_TIMEOUT)
                return False
            info = self.client.publish(
                MQTT_TOPIC,
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
                qos=MQTT_QOS,
            )
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.warning("Publish MQTT rc=%s", info.rc)
                return False
            info.wait_for_publish(timeout=MQTT_PUBLISH_TIMEOUT)
            return bool(info.is_published())
        except Exception as exc:
            logger.warning("Publish MQTT loi: %s", exc)
            return False

    def resend_failed_payload_by_tt(self, tt: int) -> None:
        found = read_failed_payload_by_tt(tt)

        # Neu file chua co trong ThatBai nhung payload con trong RAM, luu tam roi gui lai.
        if found is None:
            pending = get_pending_payload(tt)
            if pending is not None:
                try:
                    path = save_failed_payload(pending)
                    found = (path, pending)
                    logger.info("tt=%s con trong RAM, da luu tam vao %s de gui lai", tt, path)
                except Exception as exc:
                    logger.exception("Khong luu duoc pending tt=%s vao ThatBai: %s", tt, exc)

        if found is None:
            logger.warning("Khong tim thay payload tt=%s trong ThatBai de gui lai", tt)
            return

        path, payload = found
        logger.info("Dang gui lai tt=%s tu file %s", tt, path.name)
        if self.publish_payload(payload, remember_pending=True):
            try:
                path.unlink(missing_ok=True)
                logger.info("Gui lai tt=%s thanh cong -> xoa file %s", tt, path.name)
            except Exception as exc:
                logger.warning("Gui lai thanh cong nhung khong xoa duoc %s: %s", path, exc)
        else:
            logger.warning("Gui lai tt=%s that bai, giu nguyen file %s", tt, path.name)


# ─── GPIO ─────────────────────────────────────────────────────────────────────

def setup_gpio_devices():
    button = DigitalInputDevice(
        BUTTON_PIN,
        pull_up=False,    # kéo xuống GND → idle=LOW, nhấn=HIGH
        bounce_time=None, # không dùng bounce gpiozero, tự lọc bằng HIGH_STABLE_MS
    )
    internet_led = OutputDevice(INTERNET_LED_PIN, active_high=True, initial_value=False)
    mqtt_led     = OutputDevice(MQTT_LED_PIN,     active_high=True, initial_value=False)
    logger.info(
        "GPIO: nut=pin%s pull_down | HIGH lien tuc >%dms = nhan | cooldown=%.1fs",
        BUTTON_PIN, HIGH_STABLE_MS, COOLDOWN_SEC,
    )
    return button, internet_led, mqtt_led


def pin_is_high(button: DigitalInputDevice) -> bool:
    try:
        return bool(button.pin.state)
    except Exception:
        return False


# ─── LED feedback ─────────────────────────────────────────────────────────────

def signal_success(mqtt_led: OutputDevice, stop_event: threading.Event) -> None:
    mqtt_led.on()
    logger.info("MQTT da publish len broker -> LED sang 3s")
    stop_event.wait(3.0)
    mqtt_led.off()


def signal_failure(mqtt_led: OutputDevice, stop_event: threading.Event) -> None:
    logger.info("MQTT that bai -> LED nhap nhay 10s")
    for _ in range(10):
        if stop_event.is_set():
            break
        mqtt_led.on();  stop_event.wait(0.5)
        mqtt_led.off(); stop_event.wait(0.5)
    mqtt_led.off()


# ─── Chụp & gửi ───────────────────────────────────────────────────────────────

def capture_and_publish(
    mqtt_led: OutputDevice,
    mqtt_manager: MqttManager,
    stop_event: threading.Event,
) -> None:
    mqtt_led.off()
    try:
        jpeg_bytes, cam_idx = fetch_frame_from_api()
        logger.info("Lay frame OK")
    except Exception as exc:
        logger.warning("Lay frame that bai: %s", exc)
        signal_failure(mqtt_led, stop_event)
        return

    jpeg_bytes = ensure_jpeg(jpeg_bytes)
    payload = build_image_payload(jpeg_bytes, cam_idx)
    logger.info(
        "Gui MQTT tt=%s status=%s -> %s:%s topic=%s",
        payload.get("tt"), payload.get("status"), MQTT_HOST, MQTT_PORT, MQTT_TOPIC,
    )

    if mqtt_manager.publish_payload(payload, remember_pending=True):
        signal_success(mqtt_led, stop_event)
    else:
        try:
            p = save_failed_payload(payload)
            logger.error("MQTT publish that bai, luu tt=%s vao %s", payload.get("tt"), p)
        except Exception as exc:
            logger.exception("Khong luu duoc payload: %s", exc)
        signal_failure(mqtt_led, stop_event)


# ─── Thread giám sát internet ─────────────────────────────────────────────────

def internet_monitor_loop(internet_led: OutputDevice, stop_event: threading.Event) -> None:
    last: bool | None = None
    while not stop_event.is_set():
        try:
            online = internet_available()
            internet_led.on() if online else internet_led.off()
            if online != last:
                logger.info("Internet: %s", "OK" if online else "MAT KET NOI")
                last = online
        except Exception as exc:
            internet_led.off()
            logger.warning("Loi check internet: %s", exc)
        stop_event.wait(INTERNET_CHECK_INTERVAL)


# ─── Thread nút ───────────────────────────────────────────────────────────────

def button_loop(
    button: DigitalInputDevice,
    mqtt_led: OutputDevice,
    mqtt_manager: MqttManager,
    stop_event: threading.Event,
) -> None:
    """
    Mỗi POLL_MS đọc pin một lần.
    Nếu HIGH: đếm +1. Nếu LOW: reset về 0.
    Đếm đủ HIGH_STABLE_MS / POLL_MS lần liên tiếp → GỬI.
    Sau khi gửi → cooldown COOLDOWN_SEC → đếm lại từ 0.
    """
    need = max(1, HIGH_STABLE_MS // POLL_MS)
    logger.info(
        "San sang: pin%s HIGH x%d lan (%dms) -> gui | cooldown=%.1fs | poll=%dms",
        BUTTON_PIN, need, need * POLL_MS, COOLDOWN_SEC, POLL_MS,
    )

    count = 0

    while not stop_event.is_set():
        try:
            # Đọc pin
            if pin_is_high(button):
                count += 1
                if count == 1:
                    logger.debug("pin%s: bat dau dem HIGH...", BUTTON_PIN)
            else:
                if count > 0:
                    logger.debug("pin%s: ve LOW sau %d lan, reset", BUTTON_PIN, count)
                count = 0

            # Đủ thời gian HIGH → trigger
            if count >= need:
                logger.info("pin%s HIGH lien tuc %dms -> GUI ANH", BUTTON_PIN, need * POLL_MS)
                count = 0
                capture_and_publish(mqtt_led, mqtt_manager, stop_event)
                logger.info("Cooldown %.1fs", COOLDOWN_SEC)
                stop_event.wait(COOLDOWN_SEC)
                count = 0   # reset sau cooldown
            else:
                stop_event.wait(POLL_SEC)

        except Exception as exc:
            logger.exception("Loi thread nut: %s", exc)
            count = 0
            stop_event.wait(1.0)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    button, internet_led, mqtt_led = setup_gpio_devices()
    stop_event = threading.Event()
    mqtt_manager = MqttManager()
    mqtt_manager.start()

    threading.Thread(
        target=internet_monitor_loop,
        name="internet-monitor",
        args=(internet_led, stop_event),
        daemon=True,
    ).start()

    threading.Thread(
        target=pending_timeout_loop,
        name="pending-timeout",
        args=(stop_event,),
        daemon=True,
    ).start()

    threading.Thread(
        target=button_loop,
        name="button-mqtt",
        args=(button, mqtt_led, mqtt_manager, stop_event),
        daemon=True,
    ).start()

    try:
        while not stop_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Dung chuong trinh")
    finally:
        stop_event.set()
        time.sleep(0.5)
        mqtt_manager.stop()
        internet_led.off()
        mqtt_led.off()
        for dev in (button, internet_led, mqtt_led):
            try:
                dev.close()
            except Exception:
                pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
