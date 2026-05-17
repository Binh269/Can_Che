import json
import threading
import time
import base64
import os
import logging
import requests
from urllib.parse import urlparse
from datetime import datetime

import paho.mqtt.client as mqtt
from django.utils import timezone

logger = logging.getLogger(__name__)

# Khoang cach giua 2 lan lay du lieu (giay)
KHOANG_CACH_POLL = 3

_tt_lock = threading.Lock()
_tt_state_by_can = {}


def _safe_int(value):
    """Ep ve int, tra ve None neu khong hop le."""
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _lay_ngay_payload(payload):
    """Lay ngay tu thoi_gian/time de reset luong tt moi ngay."""
    if not isinstance(payload, dict):
        return datetime.now().strftime('%Y-%m-%d')

    thoi_gian = payload.get('thoi_gian') or payload.get('time') or ''
    return _parse_thoi_gian(thoi_gian).strftime('%Y-%m-%d')


def _publish_ack(client, ack_topic, tt, status):
    """Ban ACK ve DieuKhien.py: status=false de yeu cau gui lai, true de xac nhan OK."""
    if not client or not ack_topic:
        return False

    payload = {'tt': int(tt), 'status': bool(status)}
    try:
        info = client.publish(
            ack_topic,
            json.dumps(payload, ensure_ascii=False, separators=(',', ':')),
            qos=1,
        )
        if info.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"[MQTT] Da ban ACK {payload} -> {ack_topic}")
            return True
        logger.warning(f"[MQTT] Ban ACK that bai rc={info.rc}: {payload}")
    except Exception as loi:
        logger.error(f"[MQTT] Loi ban ACK {payload}: {loi}")
    return False


def _resolve_ack_topic(topic, topic_pattern, ack_topic):
    """Doi ACK topic co wildcard ve topic publish hop le."""
    if not ack_topic:
        return f'{topic}/ack'

    if '+' not in ack_topic and '#' not in ack_topic:
        return ack_topic

    phan_topic = topic.split('/')
    phan_pattern = topic_pattern.split('/')
    wildcard_values = {}
    if len(phan_topic) == len(phan_pattern):
        for index, part in enumerate(phan_pattern):
            if part == '+':
                wildcard_values[index] = phan_topic[index]

    resolved = []
    for index, part in enumerate(ack_topic.split('/')):
        if part == '+':
            resolved.append(wildcard_values.get(index, phan_topic[index] if index < len(phan_topic) else ''))
        elif part == '#':
            if index < len(phan_topic):
                resolved.extend(phan_topic[index:])
            break
        else:
            resolved.append(part)

    return '/'.join(item for item in resolved if item)


def _kiem_tra_tt_lien_tuc(ma_can, payload, client=None, ack_topic=None):
    """
    Theo doi tt da nhan theo tung can.
    Vi du nhan 1,2,4 thi phat hien thieu 3 va ban {"tt":3,"status":false}.
    """
    if not isinstance(payload, dict):
        return

    tt = _safe_int(payload.get('tt'))
    if tt is None or tt <= 0:
        return

    ngay = _lay_ngay_payload(payload)
    missing = []

    with _tt_lock:
        state = _tt_state_by_can.get(ma_can)
        if not state or state.get('ngay') != ngay:
            state = {
                'ngay': ngay,
                'last_contiguous': 0,
                'received': set(),
                'requested_missing': set(),
            }
            _tt_state_by_can[ma_can] = state

        received = state['received']
        requested_missing = state['requested_missing']
        received.add(tt)

        expected = state['last_contiguous'] + 1
        if tt > expected:
            for lost_tt in range(expected, tt):
                if lost_tt not in received and lost_tt not in requested_missing:
                    missing.append(lost_tt)
                    requested_missing.add(lost_tt)

        while state['last_contiguous'] + 1 in received:
            state['last_contiguous'] += 1
            requested_missing.discard(state['last_contiguous'])

        # Gioi han RAM: giu cac tt gan vung lien tuc hien tai.
        min_keep = max(1, state['last_contiguous'] - 200)
        state['received'] = {item for item in received if item >= min_keep}
        state['requested_missing'] = {item for item in requested_missing if item >= min_keep}

    for lost_tt in missing:
        logger.warning(f"[{ma_can}] TT khong lien tuc, thieu tt={lost_tt}")
        _publish_ack(client, ack_topic, lost_tt, False)


def _lay_ma_can_tu_topic(topic, topic_pattern):
    """Lay ma_can tu topic dua tren wildcard '+' trong topic pattern."""
    if '+' not in topic_pattern:
        return None

    phan_topic = topic.split('/')
    phan_pattern = topic_pattern.split('/')
    if len(phan_topic) != len(phan_pattern):
        return None

    for i, item in enumerate(phan_pattern):
        if item == '+':
            return phan_topic[i]
    return None


def _parse_thoi_gian(thoi_gian_chuoi):
    """Parse chuoi thoi gian ve datetime, fallback ve gio hien tai."""
    if not thoi_gian_chuoi:
        return timezone.localtime()

    parsed = None

    for dinh_dang in [
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%d/%m/%Y %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f',
    ]:
        try:
            parsed = datetime.strptime(thoi_gian_chuoi, dinh_dang)
            break
        except ValueError:
            continue

    if parsed is None:
        try:
            parsed = datetime.fromisoformat(thoi_gian_chuoi)
        except Exception:
            return timezone.localtime()

    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_default_timezone())
    return parsed.astimezone(timezone.get_default_timezone())


def lay_du_lieu_tu_api(can):
    """
    Goi API cua can, tra ve dict du lieu hoac None neu loi.
    API tra ve: {"weight": 123.5, "time": "...", "img": "base64..."}
    """
    try:
        phan_hoi = requests.get(can.api, timeout=5)
        phan_hoi.raise_for_status()
        return phan_hoi.json()
    except requests.exceptions.Timeout:
        logger.warning(f"[{can.ma_can}] API timeout")
    except requests.exceptions.ConnectionError:
        logger.warning(f"[{can.ma_can}] Khong ket noi duoc API")
    except Exception as loi:
        logger.error(f"[{can.ma_can}] Loi lay du lieu: {loi}")
    return None


def luu_anh_tir_base64(ma_can, thoi_gian, chuoi_base64):
    """
    Giai ma base64 va luu vao thu muc media/ban_ghi/.
    Tra ve duong dan tuong doi de luu vao ImageField.
    """
    try:
        # Bo phan prefix neu co (vd: "data:image/jpeg;base64,...")
        if ',' in chuoi_base64:
            chuoi_base64 = chuoi_base64.split(',', 1)[1]

        ten_file = f"{ma_can}_{thoi_gian.strftime('%Y%m%d_%H%M%S')}.jpg"
        duong_dan_tuong_doi = f"ban_ghi/{ten_file}"

        from django.conf import settings
        duong_dan_day_du = os.path.join(settings.MEDIA_ROOT, 'ban_ghi', ten_file)
        os.makedirs(os.path.dirname(duong_dan_day_du), exist_ok=True)

        with open(duong_dan_day_du, 'wb') as f:
            f.write(base64.b64decode(chuoi_base64))

        return duong_dan_tuong_doi
    except Exception as loi:
        logger.error(f"[{ma_can}] Loi luu anh: {loi}")
        return None


def _decode_base64_image(chuoi_base64):
    if not chuoi_base64:
        return None
    try:
        if ',' in chuoi_base64:
            chuoi_base64 = chuoi_base64.split(',', 1)[1]
        return base64.b64decode(chuoi_base64)
    except Exception:
        return None


def _nhan_dien_trong_luong_tu_base64(ma_can, chuoi_base64):
    anh_bytes = _decode_base64_image(chuoi_base64)
    if not anh_bytes:
        return None
    try:
        from .TrongLuong import nhan_dien_trong_luong_tu_bytes

        ket_qua = nhan_dien_trong_luong_tu_bytes(anh_bytes)
        if ket_qua.get('trong_luong_float') is not None:
            logger.info(
                f"[{ma_can}] Nhan dien trong luong: {ket_qua.get('trong_luong')}kg "
                f"raw={ket_qua.get('trong_luong_raw') or '<fail->0>'} "
                f"nguon={ket_qua.get('nguon_nhan_dien')} "
                f"tin_cay={ket_qua.get('do_tin_cay', 0):.0%}"
            )
            return ket_qua
        logger.warning(f"[{ma_can}] OCR khong doc duoc trong luong tu anh, luu 0kg")
    except Exception as loi:
        logger.error(f"[{ma_can}] Loi OCR trong luong: {loi}")
    return None


def xu_ly_du_lieu_moi(can, du_lieu):
    """
    Kiem tra du lieu moi va luu vao DB neu chua co.
    So sanh voi ban ghi cuoi cung dua tren truong 'time'.
    """
    from .models import BanGhiCan
    from django.db import connection

    try:
        thoi_gian_chuoi = du_lieu.get('time', du_lieu.get('thoi_gian', ''))
        anh_base64 = du_lieu.get('img', du_lieu.get('image', ''))
        thoi_gian = _parse_thoi_gian(thoi_gian_chuoi)

        ket_qua_ocr = _nhan_dien_trong_luong_tu_base64(can.ma_can, anh_base64) if anh_base64 else None
        if ket_qua_ocr is not None:
            khoi_luong = ket_qua_ocr.get('trong_luong_float')
        else:
            khoi_luong = du_lieu.get('weight', du_lieu.get('khoi_luong'))
            if khoi_luong is None and not anh_base64:
                khoi_luong = du_lieu.get('trong_luong')
            if khoi_luong is None:
                khoi_luong = 0.0

            try:
                khoi_luong = float(str(khoi_luong).replace(',', '.'))
            except (TypeError, ValueError):
                logger.warning(f"[{can.ma_can}] Bo qua du lieu khong hop le: {khoi_luong}")
                return False

        du_lieu_goc = dict(du_lieu)
        if ket_qua_ocr is not None:
            du_lieu_goc['trong_luong_nhan_dien'] = ket_qua_ocr.get('trong_luong')
            du_lieu_goc['trong_luong_raw'] = ket_qua_ocr.get('trong_luong_raw')
            du_lieu_goc['do_tin_cay_nhan_dien'] = ket_qua_ocr.get('do_tin_cay')

        # Kiem tra xem ban ghi nay da ton tai chua (dua tren ma_can va thoi_gian)
        da_ton_tai = BanGhiCan.objects.filter(
            can=can,
            thoi_gian=thoi_gian
        ).exists()

        if da_ton_tai:
            return True  # Du lieu cu, coi nhu da nhan OK de ACK lai cho Pi

        # Tao ban ghi moi
        ban_ghi = BanGhiCan(
            can=can,
            khoi_luong=khoi_luong,
            thoi_gian=thoi_gian,
            du_lieu_goc=json.dumps(du_lieu_goc, ensure_ascii=False),
        )

        # Luu anh neu co
        if anh_base64:
            duong_dan_anh = luu_anh_tir_base64(can.ma_can, thoi_gian, anh_base64)
            if duong_dan_anh:
                ban_ghi.anh = duong_dan_anh

        ban_ghi.save()
        logger.info(f"[{can.ma_can}] Da luu ban ghi: {khoi_luong}kg luc {thoi_gian}")
        return True

    except Exception as loi:
        logger.error(f"[{can.ma_can}] Loi xu ly du lieu: {loi}")
        return False
    finally:
        # Dong ket noi DB de tranh leak trong thread
        connection.close()


def _xu_ly_tin_nhan_mqtt(topic, payload, topic_pattern, client=None, ack_topic=None):
    """Xu ly payload MQTT va luu thanh BanGhiCan."""
    from .models import Can

    # Neu payload la chuoi dang 'image = {...}' hoac chua JSON ben trong, thu giai ma
    try:
        if isinstance(payload, str):
            # tim first '{' va last '}' de cat ra JSON
            start = payload.find('{')
            end = payload.rfind('}')
            if start != -1 and end != -1 and end > start:
                inner = payload[start:end+1]
                try:
                    payload = json.loads(inner)
                except Exception:
                    # ko phai JSON hop le, bo qua
                    logger.warning(f"[MQTT] Payload string khong phai JSON: {topic}")
        elif isinstance(payload, dict):
            # neu chi co 1 truong va gia tri la chuoi JSON, thu parse
            if len(payload) == 1:
                k = next(iter(payload.keys()))
                v = payload.get(k)
                if isinstance(v, str) and v.strip().startswith('{') and v.strip().endswith('}'):
                    try:
                        payload = json.loads(v)
                    except Exception:
                        pass
            # mot so broker tra ve dang {'image': '{...}'}
            if 'image' in payload and isinstance(payload.get('image'), str):
                imgv = payload.get('image')
                if imgv.strip().startswith('{') and imgv.strip().endswith('}'):
                    try:
                        parsed = json.loads(imgv)
                        # merge parsed object into payload (parsed wins)
                        payload = parsed
                    except Exception:
                        pass
    except Exception as e:
        logger.debug(f"[MQTT] Loi khi giai payload: {e}")

    # Hỗ trợ nhiều tên trường chứa mã cân
    ma_can = None
    if isinstance(payload, dict):
        ma_can = payload.get('ma_can') or payload.get('can') or payload.get('CAN_ID')
    if not ma_can:
        ma_can = _lay_ma_can_tu_topic(topic, topic_pattern)
    if not ma_can:
        logger.warning(f"[MQTT] Khong xac dinh duoc ma_can tu topic: {topic}")
        return

    _kiem_tra_tt_lien_tuc(ma_can, payload, client=client, ack_topic=ack_topic)

    try:
        can = Can.objects.get(ma_can=ma_can, hoat_dong=True)
    except Can.DoesNotExist:
        logger.warning(f"[MQTT] Khong tim thay can hoat dong: {ma_can}")
        return

    da_xu_ly = xu_ly_du_lieu_moi(can, payload)
    tt = _safe_int(payload.get('tt')) if isinstance(payload, dict) else None
    if da_xu_ly and tt is not None:
        _publish_ack(client, ack_topic, tt, True)


def _tao_mqtt_client(settings):
    """Tao va cau hinh MQTT client."""
    mqtt_url = getattr(settings, 'MQTT_BROKER_URL', 'mqtt://10.6.5.232:1883')
    topic_pattern = getattr(settings, 'MQTT_TOPIC_PATTERN', 'can/+/data')
    ack_topic = getattr(settings, 'MQTT_ACK_TOPIC', f'{topic_pattern}/ack')
    keepalive = int(getattr(settings, 'MQTT_KEEPALIVE', 60))
    client_id = getattr(settings, 'MQTT_CLIENT_ID', 'web_can_server')
    username = getattr(settings, 'MQTT_USERNAME', '')
    password = getattr(settings, 'MQTT_PASSWORD', '')

    parsed = urlparse(mqtt_url)
    host = parsed.hostname or 'localhost'
    port = parsed.port or 1883

    client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
    if username:
        client.username_pw_set(username, password=password or None)

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"[MQTT] Da ket noi broker {host}:{port}")
            client.subscribe(topic_pattern)
            logger.info(f"[MQTT] Da subscribe topic: {topic_pattern}")
        else:
            logger.error(f"[MQTT] Ket noi that bai, rc={rc}")

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            ack_topic_for_msg = _resolve_ack_topic(msg.topic, topic_pattern, ack_topic)
            # Hỗ trợ payload là dict hoặc list các dict
            if isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        _xu_ly_tin_nhan_mqtt(msg.topic, item, topic_pattern, client, ack_topic_for_msg)
                    else:
                        logger.warning(f"[MQTT] Item trong list khong phai dict: {msg.topic}")
                return

            if isinstance(payload, dict):
                # Nếu payload chứa danh sách trong trường 'data' hoặc 'list', xử lý từng phần tử
                if 'data' in payload and isinstance(payload['data'], list):
                    for item in payload['data']:
                        if isinstance(item, dict):
                            _xu_ly_tin_nhan_mqtt(msg.topic, item, topic_pattern, client, ack_topic_for_msg)
                    return
                if 'list' in payload and isinstance(payload['list'], list):
                    for item in payload['list']:
                        if isinstance(item, dict):
                            _xu_ly_tin_nhan_mqtt(msg.topic, item, topic_pattern, client, ack_topic_for_msg)
                    return

                _xu_ly_tin_nhan_mqtt(msg.topic, payload, topic_pattern, client, ack_topic_for_msg)

            else:
                logger.warning(f"[MQTT] Payload khong phai JSON hop le (khong la dict/list): {msg.topic}")
        except json.JSONDecodeError:
            logger.warning(f"[MQTT] Payload khong phai JSON hop le: {msg.topic}")
        except Exception as loi:
            logger.error(f"[MQTT] Loi xu ly tin nhan {msg.topic}: {loi}")

    client.on_connect = on_connect
    client.on_message = on_message

    return client, host, port, keepalive


def _vong_lap_mqtt():
    """Khoi dong MQTT loop va tu dong reconnect khi mat ket noi."""
    from django.conf import settings

    while True:
        client = None
        try:
            client, host, port, keepalive = _tao_mqtt_client(settings)
            client.connect(host, port, keepalive=keepalive)
            client.loop_forever(retry_first_connection=True)
        except Exception as loi:
            logger.error(f"[MQTT] Loi ket noi/loop: {loi}. Thu lai sau 5 giay")
            time.sleep(5)
        finally:
            try:
                if client:
                    client.disconnect()
            except Exception:
                pass


def khoi_dong_luong_mqtt():
    """Tao 1 thread subscriber MQTT cho toan bo he thong can."""
    luong = threading.Thread(
        target=_vong_lap_mqtt,
        daemon=True,
        name='luong_mqtt_can',
    )
    luong.start()
    logger.info('Da khoi dong luong MQTT cho he thong can')


def vong_lap_mot_can(ma_can):
    """
    Vong lap polling cho mot can cu the.
    Chay trong thread rieng, khong dung.
    """
    from .models import Can
    from django.db import connection

    logger.info(f"[{ma_can}] Bat dau luong polling")

    while True:
        try:
            # Lay lai thong tin can tu DB (co the da duoc cap nhat)
            can = Can.objects.get(ma_can=ma_can)

            if not can.hoat_dong:
                logger.info(f"[{ma_can}] Can da tat, dung luong")
                break

            du_lieu = lay_du_lieu_tu_api(can)
            if du_lieu:
                xu_ly_du_lieu_moi(can, du_lieu)

        except Can.DoesNotExist:
            logger.warning(f"[{ma_can}] Can khong ton tai, dung luong")
            break
        except Exception as loi:
            logger.error(f"[{ma_can}] Loi vong lap: {loi}")
        finally:
            connection.close()

        time.sleep(KHOANG_CACH_POLL)


def khoi_dong_tat_ca_luong():
    """
    Duoc goi tu apps.py khi Django khoi dong.
    Tao 1 thread rieng cho moi can dang hoat dong.
    """
    from .models import Can

    danh_sach_can = Can.objects.filter(hoat_dong=True)
    so_luong = danh_sach_can.count()
    logger.info(f"Khoi dong {so_luong} luong polling can")

    for can in danh_sach_can:
        luong = threading.Thread(
            target=vong_lap_mot_can,
            args=(can.ma_can,),
            daemon=True,  # Tu dong dung khi main process dung
            name=f"luong_can_{can.ma_can}",
        )
        luong.start()
        logger.info(f"Da khoi dong luong cho can: {can.ma_can} - {can.ten_can}")
