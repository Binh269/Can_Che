import json
import re
import base64
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from functools import wraps
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.http import require_POST
from django.contrib.sessions.models import Session
from django.utils import timezone
from .models import Can, BanGhiCan

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None

CAMERA_URL_PRESETS = {
    'Xem camera 1': [
        'http://admin:pass@10.6.5.232:5000/stream',
    ],
    'Xem camera 2': [
        'https://example.org/streams/box1',
    ],
    'Xem camera 3': [
        'https://example.org/streams/box1',
    ],
    'Xem camera 4': [
        'https://example.org/streams/box1',
    ],
}


def _bo_thong_tin_xac_thuc_url(url):
    """Bo user:pass nhung giu nguyen iframe src de browser khong chan embedded credentials."""
    if not url:
        return url

    try:
        parsed = urlparse(url)
        if not parsed.username and not parsed.password:
            return url

        clean_netloc = parsed.hostname or ''
        if parsed.port:
            clean_netloc = f'{clean_netloc}:{parsed.port}'

        return urlunparse((
            parsed.scheme,
            clean_netloc,
            parsed.path or '/',
            parsed.params,
            parsed.query,
            parsed.fragment,
        ))
    except Exception:
        return url


# ─────────────────────────────────────────────────────────────
#region TIEN ICH
# ─────────────────────────────────────────────────────────────

def kiem_tra_quyen_admin(nguoi_dung):
    """Kiem tra xem nguoi dung co quyen quan tri khong."""
    return nguoi_dung.is_superuser

# Kiểm tra quyền người dùng
def has_quyen(group_name, request):
    user = request.user
    return (
        user.is_authenticated
        and Group.objects.filter(name=group_name, user__id=user.id).exists()
    )

def check_quyen(group_name):
    """Decorator factory: use as @check_quyen('Group Name')."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if has_quyen(group_name, request):
                return view_func(request, *args, **kwargs)
            messages.error(request, "Bạn không đủ quyền để truy cập mục này!")
            return redirect('trang_chu')
        return _wrapped
    return decorator

def get_allowed_cans(request):
    """Trả về queryset các `Can` mà người dùng có quyền xem.

    Quy tắc nhóm:
    - 'Xem cân <ma_can>'
    - 'Xem cân <ten_can>'
    - 'Xem cân tất cả' (quyền xem mọi cân)
    """
    if kiem_tra_quyen_admin(request.user):
        return Can.objects.all()

    group_names = set(g.name for g in request.user.groups.all())
    if 'Xem cân tất cả' in group_names:
        return Can.objects.all()

    allowed_pks = [c.pk for c in Can.objects.all() if (
        f"Xem cân {c.ma_can}" in group_names or f"Xem cân {c.ten_can}" in group_names
    )]

    return Can.objects.filter(pk__in=allowed_pks)


def co_quyen_sua_can(request):
    """Tra ve True neu nguoi dung co quyen sua thong tin can."""
    if kiem_tra_quyen_admin(request.user):
        return True

    return (
        request.user.is_authenticated
        and Group.objects.filter(name='Sửa thông tin cân', user__id=request.user.id).exists()
    )


def _tim_thu_muc_anh_theo_ngay(thoi_gian):
    """Tra ve thu muc anh theo ngay trong data/img/(ngay)."""
    thoi_gian = timezone.localtime(thoi_gian)
    goc_anh = Path(getattr(settings, 'DATA_IMG_ROOT', settings.BASE_DIR / 'data' / 'img'))
    if not goc_anh.exists():
        return None, None

    cac_mau_ngay = [
        thoi_gian.strftime('%Y-%m-%d'),
        thoi_gian.strftime('%Y%m%d'),
        thoi_gian.strftime('%d-%m-%Y'),
    ]
    for ten_thu_muc in cac_mau_ngay:
        thu_muc = goc_anh / ten_thu_muc
        if thu_muc.exists() and thu_muc.is_dir():
            return thu_muc, ten_thu_muc
    return None, None


def _diem_anh_theo_ten(ten_file, ma_can, thoi_gian):
    """Cham diem file anh de tim anh phu hop nhat voi ban ghi can."""
    thoi_gian = timezone.localtime(thoi_gian)
    ten = ten_file.lower()
    diem = 0
    if ma_can.lower() in ten:
        diem += 100

    dau_thoi_gian = [
        thoi_gian.strftime('%Y%m%d_%H%M%S'),
        thoi_gian.strftime('%Y%m%d%H%M%S'),
        thoi_gian.strftime('%H%M%S'),
        thoi_gian.strftime('%H%M'),
    ]
    for chi_so, dau in enumerate(dau_thoi_gian):
        if dau in ten:
            diem += (40 - chi_so * 5)

    if re.search(r'can|weight|scale', ten):
        diem += 10
    return diem


def _lay_url_anh_theo_thu_muc_ngay(ma_can, thoi_gian):
    """Lay URL anh tu data/img/(ngay) theo ma_can va thoi_gian ban ghi."""
    thu_muc_ngay, ten_thu_muc = _tim_thu_muc_anh_theo_ngay(thoi_gian)
    if not thu_muc_ngay:
        return None

    danh_sach = []
    for ext in ('*.jpg', '*.jpeg', '*.png', '*.webp'):
        danh_sach.extend(thu_muc_ngay.glob(ext))
        danh_sach.extend(thu_muc_ngay.glob(ext.upper()))

    if not danh_sach:
        return None

    file_tot_nhat = max(
        danh_sach,
        key=lambda f: (_diem_anh_theo_ten(f.name, ma_can, thoi_gian), f.stat().st_mtime),
    )

    data_img_url = getattr(settings, 'DATA_IMG_URL', '/data-img/')
    return f"{data_img_url}{quote(ten_thu_muc)}/{quote(file_tot_nhat.name)}"


def _lay_url_anh_cho_ban_ghi(ban_ghi):
    """Lay URL anh cho ban ghi: uu tien media, fallback data/img/(ngay)."""
    if ban_ghi.anh:
        return ban_ghi.anh.url
    return _lay_url_anh_theo_thu_muc_ngay(ban_ghi.can.ma_can, ban_ghi.thoi_gian)


def _doc_frame_bang_cv2(url):
    if cv2 is None:
        return None
    cap = cv2.VideoCapture(url)
    try:
        if not cap.isOpened():
            return None
        ok, frame = cap.read()
        return frame if ok else None
    finally:
        cap.release()


def _giai_anh_tu_bytes(anh_bytes):
    if cv2 is None or np is None or not anh_bytes:
        return None
    arr = np.frombuffer(anh_bytes, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _lay_bytes_anh_tu_json(obj):
    if not isinstance(obj, dict):
        return None

    for key in ('image', 'image_base64', 'frame', 'frame_base64', 'img', 'data'):
        value = obj.get(key)
        if isinstance(value, str) and len(value.strip()) > 20:
            value = value.strip()
            try:
                if value.startswith('data:') and ';base64,' in value:
                    return base64.b64decode(value.split(';base64,', 1)[1])
                return base64.b64decode(value)
            except Exception:
                pass

    for key in ('image_url', 'frame_url', 'url'):
        value = obj.get(key)
        if isinstance(value, str) and value.startswith(('http://', 'https://')):
            try:
                r = requests.get(value, timeout=5)
                r.raise_for_status()
                return r.content
            except Exception:
                pass
    return None


def _lay_frame_tu_url(url):
    if not url:
        return None

    parsed = urlparse(url)
    path = (parsed.path or '').lower()
    la_luong_video = parsed.scheme in ('rtsp', 'rtmp') or any(
        item in path for item in ('stream', 'mjpeg', 'video')
    )

    if la_luong_video:
        frame = _doc_frame_bang_cv2(url)
        if frame is not None:
            return frame
        return None

    if parsed.scheme in ('http', 'https'):
        try:
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            content_type = r.headers.get('Content-Type', '')
            if 'image' in content_type:
                return _giai_anh_tu_bytes(r.content)
            if 'json' in content_type or r.text.lstrip().startswith('{'):
                return _giai_anh_tu_bytes(_lay_bytes_anh_tu_json(r.json()))
        except Exception:
            pass

    return _doc_frame_bang_cv2(url)


def _lay_url_nhan_dien_cua_can(can):
    if can.api:
        return can.api
    camera = can.cameras.filter(hoat_dong=True).exclude(api='').first()
    return camera.api if camera else ''


def _fmt_thoi_gian_vn(thoi_gian):
    """Format datetime theo timezone Viet Nam dang hien thi trong UI."""
    if not thoi_gian:
        return None
    return timezone.localtime(thoi_gian).strftime('%d/%m/%Y %H:%M:%S')


def _fmt_thoi_gian_bieu_do(thoi_gian):
    if not thoi_gian:
        return None
    return timezone.localtime(thoi_gian).strftime('%H:%M %d/%m')


def _khoang_ngay_hien_tai_vn():
    hom_nay = timezone.localdate()
    bat_dau = timezone.make_aware(datetime.combine(hom_nay, time.min), timezone.get_default_timezone())
    ket_thuc = bat_dau + timedelta(days=1)
    return bat_dau, ket_thuc


def _dem_ban_ghi_hom_nay(queryset_can):
    bat_dau, ket_thuc = _khoang_ngay_hien_tai_vn()
    return BanGhiCan.objects.filter(
        can__in=queryset_can,
        thoi_gian__gte=bat_dau,
        thoi_gian__lt=ket_thuc,
    ).count()


def _gan_du_lieu_hien_tai_cho_can(danh_sach_can):
    """Gan ban ghi moi nhat vao object Can de template render duoc ngay."""
    ket_qua = list(danh_sach_can)
    for can in ket_qua:
        ban_ghi_moi_nhat = can.ban_ghi.order_by('-thoi_gian').first()
        can.co_du_lieu_hien_tai = ban_ghi_moi_nhat is not None
        can.khoi_luong_hien_tai = ban_ghi_moi_nhat.khoi_luong if ban_ghi_moi_nhat else None
        can.thoi_gian_cap_nhat = _fmt_thoi_gian_vn(ban_ghi_moi_nhat.thoi_gian) if ban_ghi_moi_nhat else None
        if ban_ghi_moi_nhat and can.khoi_luong_toi_da:
            can.phan_tram_tai = min(100, round((ban_ghi_moi_nhat.khoi_luong / can.khoi_luong_toi_da) * 100, 1))
        else:
            can.phan_tram_tai = 0
    return ket_qua


def _lay_du_lieu_bieu_do_trang_chu(danh_sach_can):
    ket_qua = []
    for can in danh_sach_can:
        ban_ghi_list = list(can.ban_ghi.order_by('-thoi_gian')[:50])
        ban_ghi_list.reverse()
        ket_qua.append({
            'ma_can': can.ma_can,
            'ten_can': can.ten_can,
            'du_lieu': [{
                'thoi_gian': _fmt_thoi_gian_bieu_do(b.thoi_gian),
                'khoi_luong': b.khoi_luong,
            } for b in ban_ghi_list]
        })
    return ket_qua


def _lay_lich_su_trang_chu(danh_sach_can, gioi_han=30):
    ban_ghi_list = BanGhiCan.objects.filter(
        can__in=danh_sach_can
    ).order_by('-thoi_gian').select_related('can')[:gioi_han]

    return [{
        'id': b.id,
        'ma_can': b.can.ma_can,
        'ten_can': b.can.ten_can,
        'khoi_luong': b.khoi_luong,
        'thoi_gian': _fmt_thoi_gian_vn(b.thoi_gian),
        'anh': _lay_url_anh_cho_ban_ghi(b),
    } for b in ban_ghi_list]


def _dang_xuat_phien_khac(user, current_session_key):
    """Giu moi user chi co mot session dang nhap."""
    if not current_session_key:
        return

    user_id = str(user.pk)
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        if session.session_key == current_session_key:
            continue
        data = session.get_decoded()
        if str(data.get('_auth_user_id')) == user_id:
            session.delete()
#endregion


# ─────────────────────────────────────────────────────────────
#region XAC THUC
# ─────────────────────────────────────────────────────────────

def trang_dang_nhap(request):
    """Hien thi va xu ly form dang nhap."""
    if request.user.is_authenticated:
        return redirect('trang_chu')

    loi = None
    if request.method == 'POST':
        ten_dang_nhap = request.POST.get('ten_dang_nhap', '').strip()
        mat_khau = request.POST.get('mat_khau', '')
        nguoi_dung = authenticate(request, username=ten_dang_nhap, password=mat_khau)

        if nguoi_dung is not None:
            login(request, nguoi_dung)
            _dang_xuat_phien_khac(nguoi_dung, request.session.session_key)
            trang_tiep_theo = request.GET.get('next', '/')
            return redirect(trang_tiep_theo)
        else:
            loi = 'Tên đăng nhập hoặc mật khẩu không đúng.'

    return render(request, 'dang_nhap.html', {'loi': loi})


def trang_dang_xuat(request):
    """Dang xuat va chuyen ve trang dang nhap."""
    logout(request)
    return redirect('trang_dang_nhap')

#endregion


# ─────────────────────────────────────────────────────────────
#region TRANG CHU
# ─────────────────────────────────────────────────────────────

@login_required
def trang_chu(request):
    """Trang tong quan he thong."""
    danh_sach_can_qs = get_allowed_cans(request)

    # Nếu không có quyền xem cân nào, trả về trang với thông báo lỗi và danh sách rỗng
    if not danh_sach_can_qs.exists():
        thong_ke = {'tong_can': 0, 'can_hoat_dong': 0, 'tong_ban_ghi': 0}
        messages.error(request, 'Bạn không có quyền xem cân nào.')
        return render(request, 'trang_chu.html', {
            'danh_sach_can': Can.objects.none(),
            'thong_ke': thong_ke,
        })

    thong_ke = {
        'tong_can': danh_sach_can_qs.count(),
        'can_hoat_dong': danh_sach_can_qs.filter(hoat_dong=True).count(),
        'tong_ban_ghi': _dem_ban_ghi_hom_nay(danh_sach_can_qs),
    }

    danh_sach_can = _gan_du_lieu_hien_tai_cho_can(danh_sach_can_qs)
    bieu_do_trang_chu = _lay_du_lieu_bieu_do_trang_chu(danh_sach_can)
    lich_su_gan_day = _lay_lich_su_trang_chu(danh_sach_can)

    return render(request, 'trang_chu.html', {
        'danh_sach_can': danh_sach_can,
        'thong_ke': thong_ke,
        'bieu_do_trang_chu': bieu_do_trang_chu,
        'lich_su_gan_day': lich_su_gan_day,
    })


# ─────────────────────────────────────────────────────────────
#region CAN
# ─────────────────────────────────────────────────────────────

@login_required
def danh_sach_can(request):
    """Danh sach tat ca cac can."""
    danh_sach_qs = get_allowed_cans(request)
    if not danh_sach_qs.exists():
        messages.error(request, 'Bạn không có quyền xem cân nào.')
        return redirect('trang_chu')
    danh_sach = _gan_du_lieu_hien_tai_cho_can(danh_sach_qs)
    return render(request, 'danh_sach_can.html', {'danh_sach': danh_sach})


@login_required
def chi_tiet_can(request, ma_can):
    """Chi tiet mot can va lich su ban ghi."""
    can = get_object_or_404(Can, ma_can=ma_can)
    # Kiểm tra quyền với cân cụ thể
    allowed = get_allowed_cans(request)
    if not allowed.filter(pk=can.pk).exists():
        messages.error(request, 'Bạn không có quyền xem chi tiết cân này.')
        return redirect('trang_chu')

    cameras = can.cameras.filter(hoat_dong=True)
    ban_ghi_gan_nhat = can.ban_ghi.order_by('-thoi_gian')[:20]
    return render(request, 'chi_tiet_can.html', {
        'can': can,
        'cameras': cameras,
        'ban_ghi_gan_nhat': ban_ghi_gan_nhat,
        'cho_phep_sua_can': co_quyen_sua_can(request),
    })


@login_required
@require_POST
def api_sua_can(request, ma_can):
    """Cap nhat thong tin can."""
    can = get_object_or_404(Can, ma_can=ma_can)

    if not co_quyen_sua_can(request):
        return JsonResponse({'thanh_cong': False, 'loi': 'Không có quyền'}, status=403)

    try:
        du_lieu = json.loads(request.body)

        ten_can = du_lieu.get('ten_can', '').strip()
        vi_tri = du_lieu.get('vi_tri', '').strip()
        hang = du_lieu.get('hang', '').strip()
        ngay_lap_dat = du_lieu.get('ngay_lap_dat', '').strip()
        khoi_luong_toi_da = du_lieu.get('khoi_luong_toi_da', '').strip()
        api = du_lieu.get('api', '').strip()
        hoat_dong = bool(du_lieu.get('hoat_dong', False))

        if not ten_can or not vi_tri or not hang or not ngay_lap_dat or not khoi_luong_toi_da or not api:
            return JsonResponse({'thanh_cong': False, 'loi': 'Vui lòng nhập đầy đủ thông tin'})

        try:
            can.ngay_lap_dat = date.fromisoformat(ngay_lap_dat)
        except ValueError:
            return JsonResponse({'thanh_cong': False, 'loi': 'Ngày lắp đặt không hợp lệ'})

        try:
            can.khoi_luong_toi_da = float(khoi_luong_toi_da)
        except ValueError:
            return JsonResponse({'thanh_cong': False, 'loi': 'Khối lượng tối đa không hợp lệ'})

        can.ten_can = ten_can
        can.vi_tri = vi_tri
        can.hang = hang
        can.api = api
        can.hoat_dong = hoat_dong
        can.save()

        return JsonResponse({
            'thanh_cong': True,
            'can': {
                'ma_can': can.ma_can,
                'ten_can': can.ten_can,
                'vi_tri': can.vi_tri,
                'hang': can.hang,
                'ngay_lap_dat': can.ngay_lap_dat.strftime('%d/%m/%Y'),
                'khoi_luong_toi_da': can.khoi_luong_toi_da,
                'api': can.api,
                'hoat_dong': can.hoat_dong,
            }
        })
    except Exception as loi:
        return JsonResponse({'thanh_cong': False, 'loi': str(loi)})


# ─────────────────────────────────────────────────────────────
#region QUAN LY
# ─────────────────────────────────────────────────────────────
@login_required
@check_quyen('Quản lý tài khoản')
def quan_ly_nguoi_dung(request):
    """Trang quan ly danh sach nguoi dung."""
    if not kiem_tra_quyen_admin(request.user):
        return redirect('trang_chu')

    danh_sach_nguoi_dung = User.objects.all().filter(is_staff=True).prefetch_related('groups').order_by('username')
    danh_sach_nhom = Group.objects.all()
    return render(request, 'quan_ly/nguoi_dung.html', {
        'danh_sach_nguoi_dung': danh_sach_nguoi_dung,
        'danh_sach_nhom': danh_sach_nhom,
    })

@login_required
@check_quyen('Quản lý tài khoản')
def quan_ly_nhom_quyen(request):
    """Trang quan ly nhom va phan quyen."""
    if not kiem_tra_quyen_admin(request.user):
        return redirect('trang_chu')

    danh_sach_nhom = Group.objects.all().prefetch_related('user_set', 'permissions')
    danh_sach_nguoi_dung = User.objects.all().prefetch_related('groups').order_by('username').filter(is_staff=True) 

    return render(request, 'quan_ly/nhom_quyen.html', {
        'danh_sach_nhom': danh_sach_nhom,
        'danh_sach_nguoi_dung': danh_sach_nguoi_dung,
    })


# ─────────────────────────────────────────────────────────────
#region API NOI BO 
# ─────────────────────────────────────────────────────────────

@login_required
def api_tat_ca_can(request):
    """Tra ve JSON tat ca can voi ban ghi moi nhat."""
    ket_qua = []
    allowed = get_allowed_cans(request)
    for can in allowed:
        ban_ghi = can.ban_ghi.order_by('-thoi_gian').first()
        du_lieu_can = {
            'ma_can': can.ma_can,
            'ten_can': can.ten_can,
            'vi_tri': can.vi_tri,
            'hoat_dong': can.hoat_dong,
            'khoi_luong_toi_da': can.khoi_luong_toi_da,
            'khoi_luong': ban_ghi.khoi_luong if ban_ghi else None,
            'thoi_gian': _fmt_thoi_gian_vn(ban_ghi.thoi_gian) if ban_ghi else None,
            'anh': _lay_url_anh_cho_ban_ghi(ban_ghi) if ban_ghi else None,
        }
        ket_qua.append(du_lieu_can)

    return JsonResponse({
        'ket_qua': ket_qua,
        'thong_ke': {
            'tong_can': allowed.count(),
            'can_hoat_dong': allowed.filter(hoat_dong=True).count(),
            'tong_ban_ghi': _dem_ban_ghi_hom_nay(allowed),
        }
    })


@login_required
def api_du_lieu_can(request, ma_can):
    """Tra ve JSON ban ghi moi nhat cua mot can."""
    can = get_object_or_404(Can, ma_can=ma_can)
    # Kiểm tra quyền xem cân
    if not get_allowed_cans(request).filter(pk=can.pk).exists():
        return JsonResponse({'thanh_cong': False, 'loi': 'Không có quyền'}, status=403)

    ban_ghi = can.ban_ghi.order_by('-thoi_gian').first()

    if not ban_ghi:
        return JsonResponse({'co_du_lieu': False})

    return JsonResponse({
        'co_du_lieu': True,
        'khoi_luong': ban_ghi.khoi_luong,
        'thoi_gian': _fmt_thoi_gian_vn(ban_ghi.thoi_gian),
        'anh': _lay_url_anh_cho_ban_ghi(ban_ghi),
    })


@login_required
def api_nhan_dien_trong_luong_can(request, ma_can):
    """Nhan dien trong luong truc tuyen tu frame camera/API cua can."""
    can = get_object_or_404(Can, ma_can=ma_can)
    if not get_allowed_cans(request).filter(pk=can.pk).exists():
        return JsonResponse({'thanh_cong': False, 'loi': 'Khong co quyen'}, status=403)

    url = _lay_url_nhan_dien_cua_can(can)
    if not url:
        return JsonResponse({'co_du_lieu': False, 'loi': 'Can chua co URL camera/API'}, status=400)

    frame = _lay_frame_tu_url(url)
    if frame is None:
        return JsonResponse({'co_du_lieu': False, 'loi': 'Khong lay duoc frame'}, status=502)

    try:
        from .TrongLuong import nhan_dien_trong_luong_tu_bgr

        ket_qua = nhan_dien_trong_luong_tu_bgr(frame)
    except Exception as loi:
        return JsonResponse({'co_du_lieu': False, 'loi': f'Loi OCR: {loi}'}, status=500)

    if ket_qua.get('trong_luong_float') is None:
        ket_qua = {
            'trong_luong': '0.00',
            'trong_luong_raw': '',
            'trong_luong_float': 0.0,
            'do_tin_cay': 0.0,
            'thoi_gian_ms': 0.0,
            'nguon_nhan_dien': 'fallback_0',
        }

    return JsonResponse({
        'co_du_lieu': True,
        'khoi_luong': ket_qua.get('trong_luong_float'),
        'trong_luong': ket_qua.get('trong_luong'),
        'trong_luong_raw': ket_qua.get('trong_luong_raw'),
        'do_tin_cay': ket_qua.get('do_tin_cay'),
        'nguon_nhan_dien': ket_qua.get('nguon_nhan_dien'),
        'thoi_gian_ms': ket_qua.get('thoi_gian_ms'),
        'thoi_gian': _fmt_thoi_gian_vn(timezone.now()),
    })


@login_required
def api_lich_su_can(request, ma_can):
    """Tra ve JSON lich su ban ghi cua mot can (co phan trang)."""
    can = get_object_or_404(Can, ma_can=ma_can)
    # Kiểm tra quyền xem cân
    if not get_allowed_cans(request).filter(pk=can.pk).exists():
        return JsonResponse({'thanh_cong': False, 'loi': 'Không có quyền'}, status=403)
    trang = max(1, int(request.GET.get('trang', 1)))
    so_hang = 20
    bat_dau = (trang - 1) * so_hang

    danh_sach = can.ban_ghi.order_by('-thoi_gian')[bat_dau:bat_dau + so_hang]
    tong = can.ban_ghi.count()

    du_lieu = [{
        'id': b.id,
        'khoi_luong': b.khoi_luong,
        'thoi_gian': _fmt_thoi_gian_vn(b.thoi_gian),
        'anh': _lay_url_anh_cho_ban_ghi(b),
    } for b in danh_sach]

    return JsonResponse({
        'ban_ghi': du_lieu,
        'tong': tong,
        'trang': trang,
        'so_trang': max(1, (tong + so_hang - 1) // so_hang),
    })


@login_required
def api_bieu_do_trang_chu(request):
    """Tra ve JSON lich su 50 ban ghi gan nhat cua tung can (ve bieu do)."""
    return JsonResponse({'ket_qua': _lay_du_lieu_bieu_do_trang_chu(get_allowed_cans(request))})


@login_required
def api_lich_su_trang_chu(request):
    """Tra ve JSON 30 ban ghi moi nhat cua tat ca can."""
    return JsonResponse({'ban_ghi': _lay_lich_su_trang_chu(get_allowed_cans(request))})




# ─────────────────────────────────────────────────────────────
#region NGUOI DUNG
# ─────────────────────────────────────────────────────────────
@login_required
@check_quyen('Quản lý tài khoản')
@require_POST
def api_tao_tai_khoan(request):
    """Tao tai khoan nguoi dung moi."""
    if not kiem_tra_quyen_admin(request.user):
        return JsonResponse({'thanh_cong': False, 'loi': 'Không có quyền'})
    try:
        du_lieu = json.loads(request.body)
        ten_dang_nhap = du_lieu.get('ten_dang_nhap', '').strip()
        mat_khau = du_lieu.get('mat_khau', '')
        mat_khau_check = du_lieu.get('mat_khau_check', '')
        ho_ten = du_lieu.get('ho_ten', '')
        email = du_lieu.get('email', '')
        is_admin = du_lieu.get('is_admin', False)

        if not ten_dang_nhap or not mat_khau or not mat_khau_check:
            return JsonResponse({'thanh_cong': False, 'loi': 'Tên đăng nhập và mật khẩu không được để trống'})

        if mat_khau != mat_khau_check:
            return JsonResponse({'thanh_cong': False, 'loi': 'Mật khẩu không khớp'})

        if User.objects.filter(username=ten_dang_nhap).exists():
            return JsonResponse({'thanh_cong': False, 'loi': 'Tên đăng nhập đã tồn tại'})

        nguoi_dung = User.objects.create_user(
            username=ten_dang_nhap,
            password=mat_khau,
            email=email,
            is_staff=True,
            is_superuser=is_admin
        )
        nguoi_dung.last_name = ho_ten
        nguoi_dung.save()

        return JsonResponse({'thanh_cong': True, 'id': nguoi_dung.id, 'ten': ten_dang_nhap})
    except Exception as loi:
        return JsonResponse({'thanh_cong': False, 'loi': str(loi)})


@login_required
@check_quyen('Quản lý tài khoản')
@require_POST
def api_xoa_tai_khoan(request, nguoi_dung_id):
    """Xoa tai khoan nguoi dung."""
    if not kiem_tra_quyen_admin(request.user):
        return JsonResponse({'thanh_cong': False, 'loi': 'Không có quyền'})
    if request.user.id == nguoi_dung_id:
        return JsonResponse({'thanh_cong': False, 'loi': 'Không thể xóa tài khoản đang đăng nhập'})
    try:
        nguoi_dung = get_object_or_404(User, id=nguoi_dung_id)
        nguoi_dung.is_active = False
        nguoi_dung.save()
        return JsonResponse({'thanh_cong': True})
    except Exception as loi:
        return JsonResponse({'thanh_cong': False, 'loi': str(loi)})


@login_required
@check_quyen('Quản lý tài khoản')
@require_POST
def api_cap_nhat_nhom_nguoi_dung(request, nguoi_dung_id):
    """Cap nhat nhom cua nguoi dung."""
    if not kiem_tra_quyen_admin(request.user):
        return JsonResponse({'thanh_cong': False, 'loi': 'Không có quyền'})
    try:
        du_lieu = json.loads(request.body)
        nhom_ids = du_lieu.get('nhom_ids', [])
        nguoi_dung = get_object_or_404(User, id=nguoi_dung_id)
        nhom_list = Group.objects.filter(id__in=nhom_ids)
        nguoi_dung.groups.set(nhom_list)
        return JsonResponse({'thanh_cong': True})
    except Exception as loi:
        return JsonResponse({'thanh_cong': False, 'loi': str(loi)})



# ─────────────────────────────────────────────────────────────
#region TAI KHOAN
# ─────────────────────────────────────────────────────────────

@login_required
@check_quyen('Quản lý tài khoản')
@require_POST
def api_sua_tai_khoan(request, nguoi_dung_id):
    """Sua thong tin tai khoan (username, ho_ten, email)."""
    if not kiem_tra_quyen_admin(request.user):
        return JsonResponse({'thanh_cong': False, 'loi': 'Không có quyền'})
    try:
        du_lieu = json.loads(request.body)
        nguoi_dung = get_object_or_404(User, id=nguoi_dung_id)
        nguoi_dung.last_name = du_lieu.get('ho_ten', nguoi_dung.last_name)
        nguoi_dung.email = du_lieu.get('email', nguoi_dung.email)
        nguoi_dung.save()
        return JsonResponse({'thanh_cong': True, 'ten': nguoi_dung.username})
    except Exception as loi:
        return JsonResponse({'thanh_cong': False, 'loi': str(loi)})


@login_required
@check_quyen('Quản lý tài khoản')
@require_POST
def api_khoa_tai_khoan(request, nguoi_dung_id):
    """Khoa hoac mo khoa tai khoan (toggle is_active)."""
    if not kiem_tra_quyen_admin(request.user):
        return JsonResponse({'thanh_cong': False, 'loi': 'Không có quyền'})
    if request.user.id == nguoi_dung_id:
        return JsonResponse({'thanh_cong': False, 'loi': 'Không thể khóa tài khoản đang đăng nhập'})
    try:
        nguoi_dung = get_object_or_404(User, id=nguoi_dung_id)
        nguoi_dung.is_active = not nguoi_dung.is_active
        nguoi_dung.save()
        return JsonResponse({'thanh_cong': True, 'dang_khoa': not nguoi_dung.is_active})
    except Exception as loi:
        return JsonResponse({'thanh_cong': False, 'loi': str(loi)})


@login_required
@check_quyen('Quản lý tài khoản')
@require_POST
def api_reset_mat_khau(request, nguoi_dung_id):
    """Dat lai mat khau cho tai khoan."""
    if not kiem_tra_quyen_admin(request.user):
        return JsonResponse({'thanh_cong': False, 'loi': 'Không có quyền'})
    try:
        du_lieu = json.loads(request.body)
        mat_khau_moi = du_lieu.get('mat_khau_moi', '').strip()
        if len(mat_khau_moi) < 6:
            return JsonResponse({'thanh_cong': False, 'loi': 'Mật khẩu phải từ 6 ký tự trở lên'})
        nguoi_dung = get_object_or_404(User, id=nguoi_dung_id)
        nguoi_dung.set_password(mat_khau_moi)
        nguoi_dung.save()
        return JsonResponse({'thanh_cong': True})
    except Exception as loi:
        return JsonResponse({'thanh_cong': False, 'loi': str(loi)})


@login_required
@check_quyen('Quản lý tài khoản')
@require_POST
def api_cap_quyen_admin(request, nguoi_dung_id):
    """Cap hoac thu hoi quyen admin (toggle is_staff)."""
    if not request.user.is_staff:
        return JsonResponse({'thanh_cong': False, 'loi': 'Chỉ có admin mới có quyền này'})
    if request.user.id == nguoi_dung_id:
        return JsonResponse({'thanh_cong': False, 'loi': 'Không thể thay đổi quyền admin của chính mình'})
    try:
        nguoi_dung = get_object_or_404(User, id=nguoi_dung_id)
        nguoi_dung.is_staff = not nguoi_dung.is_staff
        nguoi_dung.save()
        return JsonResponse({'thanh_cong': True, 'la_admin': nguoi_dung.is_staff})
    except Exception as loi:
        return JsonResponse({'thanh_cong': False, 'loi': str(loi)})


@login_required
@require_POST
def api_cap_nhat_ca_nhan(request):
    """Cap nhat thong tin ca nhan cua nguoi dang dang nhap."""
    try:
        du_lieu = json.loads(request.body)
        nguoi_dung = request.user
        ho_ten = du_lieu.get('ho_ten', '').strip()
        email = du_lieu.get('email', '').strip()
        mat_khau_cu = du_lieu.get('mat_khau_cu', '')
        mat_khau_moi = du_lieu.get('mat_khau_moi', '').strip()

        nguoi_dung.last_name = ho_ten
        nguoi_dung.email = email

        if mat_khau_moi:
            if not nguoi_dung.check_password(mat_khau_cu):
                return JsonResponse({'thanh_cong': False, 'loi': 'Mật khẩu cũ không đúng'})
            if len(mat_khau_moi) < 6:
                return JsonResponse({'thanh_cong': False, 'loi': 'Mật khẩu mới phải từ 6 ký tự trở lên'})
            nguoi_dung.set_password(mat_khau_moi)

        nguoi_dung.save()
        return JsonResponse({'thanh_cong': True})
    except Exception as loi:
        return JsonResponse({'thanh_cong': False, 'loi': str(loi)})



# ─────────────────────────────────────────────────────────────
#region Camera
# ─────────────────────────────────────────────────────────────

@login_required
def xem_camera(request):
    """Trang xem camera chung.

    - Neu co query param `can`, hien camera DB gan voi can do.
    - Neu khong, hien danh sach preset trong CAMERA_URL_PRESETS.
    """
    can_duoc_chon = request.GET.get('can')
    urls = []

    if can_duoc_chon:
        can = get_object_or_404(Can, ma_can=can_duoc_chon)
        if not get_allowed_cans(request).filter(pk=can.pk).exists():
            messages.error(request, 'Bạn không có quyền xem camera của cân này.')
            return redirect('trang_chu')

        urls = [_bo_thong_tin_xac_thuc_url(cam.api) for cam in can.cameras.filter(hoat_dong=True).exclude(api='')]
    else:
        group_names = set(g.name for g in request.user.groups.all())
        for name, preset in CAMERA_URL_PRESETS.items():
            if name in group_names:
                for u in preset:
                    if u:
                        urls.append(_bo_thong_tin_xac_thuc_url(u))
                        break

    return render(request, 'xem_camera.html', {'camera_urls': urls})


@login_required
@require_POST
def api_webrtc_http_proxy(request):
    """Proxy offer/answer WebRTC HTTP de tranh loi CORS tu browser."""
    try:
        du_lieu = json.loads(request.body or '{}')
        target_url = (du_lieu.get('target_url') or '').strip()
        sdp_offer = du_lieu.get('sdp_offer') or ''

        if not target_url or not sdp_offer:
            return JsonResponse({'thanh_cong': False, 'loi': 'Thiếu target_url hoặc sdp_offer'}, status=400)

        parsed = urlparse(target_url)
        headers = {'Content-Type': 'application/sdp'}
        auth = None

        if parsed.username:
            auth = (parsed.username, parsed.password or '')

        clean_netloc = parsed.hostname or ''
        if parsed.port:
            clean_netloc = f'{clean_netloc}:{parsed.port}'

        clean_url = urlunparse((
            parsed.scheme,
            clean_netloc,
            parsed.path or '/',
            parsed.params,
            parsed.query,
            parsed.fragment,
        ))

        phan_hoi = requests.post(
            clean_url,
            data=sdp_offer.encode('utf-8'),
            headers=headers,
            auth=auth,
            timeout=20,
        )

        if not phan_hoi.ok:
            return JsonResponse({
                'thanh_cong': False,
                'loi': f'Camera tra ve loi HTTP {phan_hoi.status_code}',
                'chi_tiet': phan_hoi.text[:1000],
            }, status=502)

        sdp_answer = phan_hoi.text.strip()
        if not sdp_answer:
            return JsonResponse({'thanh_cong': False, 'loi': 'Camera khong tra ve SDP answer'}, status=502)

        return JsonResponse({'thanh_cong': True, 'sdp_answer': sdp_answer})
    except requests.RequestException as loi:
        return JsonResponse({'thanh_cong': False, 'loi': f'Lỗi kết nối camera: {loi}'}, status=502)
    except Exception as loi:
        return JsonResponse({'thanh_cong': False, 'loi': str(loi)}, status=500)
