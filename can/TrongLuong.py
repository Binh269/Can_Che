import os
import sys
import json
import time
import threading
import numpy as np
import cv2
import onnxruntime as ort

# ============================================================
# CAU HINH CHUNG
# ============================================================
THU_MUC_HIEN_TAI = os.path.dirname(os.path.abspath(__file__))
THU_MUC_WEIGHTS = os.path.join(THU_MUC_HIEN_TAI, "model", "weights")


def _chon_yolo_weights_mac_dinh():
    for ten_file in (
        "trong_luong_yolo_best.pt",
        "yolo_best.pt",
        "best.pt",
        "trong_luong_yolo_best.onnx",
        "best.onnx",
    ):
        duong_dan = os.path.join(THU_MUC_WEIGHTS, ten_file)
        if os.path.exists(duong_dan):
            return duong_dan
    return ""


DUONG_DAN_ONNX  = os.environ.get(
    "TRONG_LUONG_ONNX",
    os.path.join(THU_MUC_WEIGHTS, "seven_seg.onnx"),
)
FILE_THONG_TIN  = os.environ.get(
    "TRONG_LUONG_CLASS_INFO",
    os.path.join(THU_MUC_WEIGHTS, "class_info.json"),
)
DUONG_DAN_YOLO = os.environ.get(
    "TRONG_LUONG_YOLO",
    _chon_yolo_weights_mac_dinh(),
)
YOLO_CONF = float(os.environ.get("TRONG_LUONG_YOLO_CONF", "0.25"))

# Giong Xu_Ly/Teo_nua.py — ONNX class -> ky tu hien thi
MAP_LOP_KY_TU = {
    '0':'0','1':'1','2':'2','3':'3','4':'4',
    '5':'5','6':'6','7':'7','8':'8','9':'9',
    '0_':'0.','1_':'1.','2_':'2.','3_':'3.','4_':'4.',
    '5_':'5.','6_':'6.','7_':'7.','8_':'8.','9_':'9.',
    '_0':'.0','_1':'.1','_2':'.2','_3':'.3','_4':'.4',
    '_5':'.5','_6':'.6','_7':'.7','_8':'.8','_9':'.9',
    'dot':'.','dash':'-','blank':'',
    'n':'n','o':'o','t':'t','r':'r'
}

SO_KY_TU = 5

# Mo rong crop phai khi cat tu roi_te (giong Teo_nua)
DOT_CAPTURE_PAD = 1
NGUONG_VIEN_SANG = 60
PADDING_VIEN     = 3
PAD_O            = 0
GOC_DESKEW_GIOI_HAN = 10

# Anh camera co dinh: cat truoc vung man can o goc phai duoi,
# sau do cac buoc nhan dien ben duoi chay nhu cu tren ROI nay.
DUNG_ROI_CO_DINH_GOC_PHAI_DUOI = os.environ.get("TRONG_LUONG_DUNG_ROI", "1") != "0"
ROI_PHAI_DUOI_X0_TY_LE = float(os.environ.get("TRONG_LUONG_ROI_X0", "0.22"))
ROI_PHAI_DUOI_Y0_TY_LE = float(os.environ.get("TRONG_LUONG_ROI_Y0", "0.18"))
ROI_PHAI_DUOI_X1_TY_LE = float(os.environ.get("TRONG_LUONG_ROI_X1", "1.00"))
ROI_PHAI_DUOI_Y1_TY_LE = float(os.environ.get("TRONG_LUONG_ROI_Y1", "1.00"))

# Crop sat vung hien thi "Trong Luong (kg)" trong khung camera co dinh.
# Giu bang bien moi de khong anh huong pipeline ONNX cu.
ROI_HIEN_THI_X0_TY_LE = float(os.environ.get("TRONG_LUONG_DISPLAY_X0", "0.45"))
ROI_HIEN_THI_Y0_TY_LE = float(os.environ.get("TRONG_LUONG_DISPLAY_Y0", "0.52"))
ROI_HIEN_THI_X1_TY_LE = float(os.environ.get("TRONG_LUONG_DISPLAY_X1", "0.98"))
ROI_HIEN_THI_Y1_TY_LE = float(os.environ.get("TRONG_LUONG_DISPLAY_Y1", "0.88"))

# Chia co dinh vung hien thi thanh 5 o doc tung chu so. Neu camera/crop
# lech, chi can sua cac bien moi truong TRONG_LUONG_SLOT_*.
SO_O_HIEN_THI_CO_DINH = int(os.environ.get("TRONG_LUONG_DISPLAY_SLOTS", str(SO_KY_TU)))
TAM_O_HIEN_THI_TY_LE = os.environ.get(
    "TRONG_LUONG_SLOT_CENTERS",
    "0.205,0.348,0.515,0.694,0.857",
)
O_HIEN_THI_Y0_TY_LE = float(os.environ.get("TRONG_LUONG_SLOT_Y0", "0.28"))
O_HIEN_THI_Y1_TY_LE = float(os.environ.get("TRONG_LUONG_SLOT_Y1", "0.98"))
O_HIEN_THI_W_TY_LE = float(os.environ.get("TRONG_LUONG_SLOT_W", "0.145"))
O_HIEN_THI_W_TY_LE_CHUOI = os.environ.get("TRONG_LUONG_SLOT_WIDTHS", "")
O_HIEN_THI_MIN_LED_PIX = int(os.environ.get("TRONG_LUONG_SLOT_MIN_LED", "120"))


# ============================================================
# CAC HAM TIEN ICH
# ============================================================

def cat_roi_co_dinh_goc_phai_duoi(anh_bgr):
    if not DUNG_ROI_CO_DINH_GOC_PHAI_DUOI:
        H, W = anh_bgr.shape[:2]
        return anh_bgr, (0, 0, W, H)

    H, W = anh_bgr.shape[:2]
    x0 = int(round(W * ROI_PHAI_DUOI_X0_TY_LE))
    y0 = int(round(H * ROI_PHAI_DUOI_Y0_TY_LE))
    x1 = int(round(W * ROI_PHAI_DUOI_X1_TY_LE))
    y1 = int(round(H * ROI_PHAI_DUOI_Y1_TY_LE))

    x0 = max(0, min(x0, W - 2))
    y0 = max(0, min(y0, H - 2))
    x1 = max(x0 + 1, min(x1, W))
    y1 = max(y0 + 1, min(y1, H))
    return anh_bgr[y0:y1, x0:x1].copy(), (x0, y0, x1, y1)


def cat_roi_hien_thi_trong_luong(anh_bgr):
    H, W = anh_bgr.shape[:2]
    x0 = int(round(W * ROI_HIEN_THI_X0_TY_LE))
    y0 = int(round(H * ROI_HIEN_THI_Y0_TY_LE))
    x1 = int(round(W * ROI_HIEN_THI_X1_TY_LE))
    y1 = int(round(H * ROI_HIEN_THI_Y1_TY_LE))

    x0 = max(0, min(x0, W - 2))
    y0 = max(0, min(y0, H - 2))
    x1 = max(x0 + 1, min(x1, W))
    y1 = max(y0 + 1, min(y1, H))
    return anh_bgr[y0:y1, x0:x1].copy(), (x0, y0, x1, y1)


def tim_bien_trai_theo_gradient(anh_bgr, x_bat_dau, nguong=8, window=3, pad=2):
    anh_gray = cv2.cvtColor(anh_bgr, cv2.COLOR_BGR2GRAY)
    W = anh_gray.shape[1]
    if x_bat_dau <= 0:
        return 0
    def tb_cot(x):
        x0 = max(0, x - window // 2)
        x1 = min(W, x + window // 2 + 1)
        return float(np.mean(anh_gray[:, x0:x1]))
    tb_hien = tb_cot(x_bat_dau)
    x = x_bat_dau - 1
    while x >= 0:
        tb_ke = tb_cot(x)
        if tb_ke - tb_hien >= nguong:
            return max(0, x - pad)
        tb_hien = tb_ke
        x -= 1
    return 0


def tinh_softmax(x):
    e = np.exp(x - np.max(x))
    return e / e.sum()


def bien_doi_khu_bloom(mang_uint8):
    """
    Chuan bi 32x32 cho ONNX — giong Teo_nua.py (net mong, khong dilate/close lam day bloom).
    """
    if mang_uint8 is None or mang_uint8.size == 0:
        return np.zeros((32, 32), dtype=np.uint8)
    if mang_uint8.ndim == 3:
        mang_uint8 = cv2.cvtColor(mang_uint8, cv2.COLOR_BGR2GRAY)
    rs64 = cv2.resize(mang_uint8, (64, 64), interpolation=cv2.INTER_AREA)
    mx   = float(rs64.max())
    if mx < 1.0:
        return np.zeros((32, 32), dtype=np.uint8)
    nguong = max(50.0, mx * 0.75)
    _, binary = cv2.threshold(rs64, nguong, 255, cv2.THRESH_BINARY)
    return cv2.resize(binary, (32, 32), interpolation=cv2.INTER_AREA)


def tien_xu_ly_vung_te_nua(roi_bgr, bo_doc):
    """
    Tien xu ly mau / hinh hoc giong Xu_Ly/Teo_nua.py (gray -> nhi phan -> dao ->
    lam mo -> vien -> shear). Tra ve anh xam inverted da chinh shear.
    """
    if roi_bgr is None or roi_bgr.size == 0:
        return None
    roi_gray = (cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
                if len(roi_bgr.shape) == 3 else roi_bgr.copy())
    diem_sang = roi_gray[roi_gray > 0]
    if len(diem_sang) > 0:
        nguong_thr = min(255, float(np.mean(diem_sang) * 1.5))
        _, binary = cv2.threshold(roi_gray, nguong_thr, 255, cv2.THRESH_BINARY)
    else:
        binary = roi_gray.copy()

    binary = cv2.resize(binary, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    roi_inv = cv2.bitwise_not(binary)
    roi_inv = cv2.GaussianBlur(roi_inv, (3, 3), 0)
    roi_inv = cv2.copyMakeBorder(roi_inv, 40, 40, 40, 40,
                                  cv2.BORDER_CONSTANT, value=255)

    vien_w      = int(roi_inv.shape[0] * 0.4)
    roi_inv_pad = cv2.copyMakeBorder(roi_inv, 0, 0, vien_w, vien_w,
                                       cv2.BORDER_CONSTANT, value=255)
    chu_sang    = 255 - roi_inv_pad
    sf          = bo_doc.xac_dinh_shear_de_thang(chu_sang)

    H_inv, W_inv = roi_inv_pad.shape
    pad_x = max(8, int(abs(sf) * H_inv) + 8)
    pad_y = max(6, int(0.08 * H_inv) + 4)
    roi_inv_for_shear = cv2.copyMakeBorder(
        roi_inv_pad, pad_y, pad_y, pad_x, pad_x,
        cv2.BORDER_CONSTANT, value=255
    )
    H2, W2  = roi_inv_for_shear.shape
    M_shear = np.float32([[1, sf, -sf * H2 / 2.0], [0, 1, 0]])
    roi_inv_deskew = cv2.warpAffine(
        roi_inv_for_shear, M_shear, (W2, H2),
        borderMode=cv2.BORDER_CONSTANT, borderValue=255
    )
    if roi_inv_deskew.shape[0] >= H_inv and roi_inv_deskew.shape[1] >= W_inv:
        cy   = roi_inv_deskew.shape[0] // 2
        cx   = roi_inv_deskew.shape[1] // 2
        y0_c = max(0, cy - H_inv // 2)
        x0_c = max(0, cx - W_inv // 2)
        roi_inv_deskew = roi_inv_deskew[y0_c:y0_c+H_inv, x0_c:x0_c+W_inv]
    return roi_inv_deskew


def chia_o_snap_proj_roi_te(roi_te, crop_y0, crop_y1, W_v, n_o, pad_o=0):
    """
    Chia n_o cot theo bien giong Teo (roi_te): ranh cong snap xuong thung lung
    histogram (net toi theo cot) — tranh cat ngang chu khi chia deu.
    Tra ve:
      hop_vung : [(s_x,e_x)] trong toa do vung_so (de ve buoc_05, tien_xu_ly_o)
      hop_te   : [(s_te,e_te)] trong toa do roi_te (de crop ONNX — trung khop buoc_05b)
    """
    Ht, Wt = roi_te.shape[:2]
    if crop_y1 <= crop_y0:
        crop_y0, crop_y1 = 0, Ht
    band = roi_te[crop_y0:crop_y1, :]
    proj = np.sum(band < 128, axis=0).astype(np.float64)
    mx = float(np.max(proj)) + 1e-6
    proj_n = proj / mx
    k = max(5, min(21, Wt // 25))
    if k % 2 == 0:
        k += 1
    proj_s = cv2.GaussianBlur(proj_n.reshape(1, -1), (1, k), 0).flatten()

    half_win = max(4, Wt // (n_o * 5))
    edges_te = [0]
    for bi in range(1, n_o):
        ideal = int(round(bi * Wt / n_o))
        lo = max(1, ideal - half_win)
        hi = min(Wt - 2, ideal + half_win)
        if lo >= hi:
            edges_te.append(ideal)
        else:
            loc = lo + int(np.argmin(proj_s[lo : hi + 1]))
            edges_te.append(loc)
    edges_te.append(Wt)

    for i in range(1, len(edges_te)):
        if edges_te[i] <= edges_te[i - 1]:
            edges_te[i] = edges_te[i - 1] + 1

    hop_te = []
    for i in range(n_o):
        s_te = edges_te[i]
        e_te = edges_te[i + 1]
        if e_te <= s_te:
            e_te = min(Wt, s_te + 1)
        hop_te.append((s_te, e_te))

    hop_vung = []
    for s_te, e_te in hop_te:
        s_x = int(round(s_te * W_v / max(1, Wt))) + pad_o
        e_x = int(round(e_te * W_v / max(1, Wt))) - pad_o
        s_x = max(0, min(s_x, W_v - 2))
        e_x = max(s_x + 1, min(e_x, W_v))
        hop_vung.append((s_x, e_x))
    return hop_vung, hop_te


def hieu_chinh_shear_vung_bgr(vung_bgr, bo_doc):
    """
    Can bang shear (hang so nghieng) truoc khi chia o thang dung.
    Uoc luong sf tu kenh do sang, warpAffine BGR giong logic Teo_nua.
    """
    if vung_bgr is None or vung_bgr.size == 0:
        return vung_bgr, 0.0
    chu_sang, _ = bo_doc.tach_kenh_do(vung_bgr)
    if float(chu_sang.max()) < 15.0:
        return vung_bgr, 0.0
    H, W = chu_sang.shape[:2]
    sf = bo_doc.xac_dinh_shear_de_thang(chu_sang)
    if abs(sf) < 0.008:
        return vung_bgr, sf
    pad_x = max(8, int(abs(sf) * H) + 12)
    pad_y = max(6, int(0.08 * H) + 4)
    padded = cv2.copyMakeBorder(
        vung_bgr, pad_y, pad_y, pad_x, pad_x,
        cv2.BORDER_REPLICATE
    )
    H2, W2 = padded.shape[:2]
    M = np.float32([[1, sf, -sf * H2 / 2.0], [0, 1, 0]])
    warped = cv2.warpAffine(
        padded, M, (W2, H2),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE
    )
    cy, cx = H2 // 2, W2 // 2
    y0 = max(0, min(cy - H // 2, H2 - H))
    x0 = max(0, min(cx - W // 2, W2 - W))
    out = warped[y0:y0 + H, x0:x0 + W]
    if out.shape[0] != H or out.shape[1] != W:
        out = cv2.resize(out, (W, H), interpolation=cv2.INTER_LINEAR)
    return out, sf


def tao_panel_ky_tu(cac_anh_ky_tu, cac_nhan_conf, ds_blank=None,
                    mau_nhan=(0, 255, 100),
                    cac_rong_o_px=None, cao_tham_chieu_px=None):
    """
    cac_rong_o_px     : rong moi cot (px) — nen trung buoc cat ONNX (roi_te: e_te - s_te).
    cao_tham_chieu_px : cao vung chua net so dung cho ty le (band roi_te hoac H_v).
                        rong hien thi = rong_px * CAO_KY / cao_tham_chieu_px.
    """
    CAO_KY, CAO_NHAN = 64, 22
    TONG_CAO = CAO_KY + CAO_NHAN
    if not cac_anh_ky_tu:
        anh_trong = np.zeros((TONG_CAO, 160, 3), dtype=np.uint8)
        cv2.putText(anh_trong, "(khong co ky tu)", (4, TONG_CAO-6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (90, 90, 90), 1)
        return anh_trong
    if ds_blank is None:
        ds_blank = [False] * len(cac_anh_ky_tu)
    cac_khung = []
    chuan = max(1, cao_tham_chieu_px or CAO_KY)
    for idx, (anh_kt, (ky, conf)) in enumerate(zip(cac_anh_ky_tu, cac_nhan_conf)):
        if cac_rong_o_px is not None and idx < len(cac_rong_o_px):
            # Ty le dung voi cat tu roi_te / band — tranh lech voi buoc_05b
            rong = max(16, int(cac_rong_o_px[idx] * CAO_KY / chuan))
        else:
            ty   = CAO_KY / max(1, anh_kt.shape[0])
            rong = max(16, int(anh_kt.shape[1] * ty))
        anh_r = cv2.resize(anh_kt, (rong, CAO_KY), interpolation=cv2.INTER_AREA)
        khung = np.zeros((TONG_CAO, rong+4, 3), dtype=np.uint8)
        if ds_blank[idx]:
            khung[:, :] = (30, 30, 30)
        khung[CAO_NHAN:, 2:-2] = cv2.cvtColor(anh_r, cv2.COLOR_GRAY2BGR)
        nhan_str = "[ ]" if ds_blank[idx] else f"'{ky}' {conf:.0%}"
        (tw, _), _ = cv2.getTextSize(nhan_str, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        tx = max(2, (rong - tw) // 2)
        mau_txt = (100, 100, 100) if ds_blank[idx] else mau_nhan
        cv2.putText(khung, nhan_str, (tx, CAO_NHAN-4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, mau_txt, 1, cv2.LINE_AA)
        ke = np.full((TONG_CAO, 2, 3), (55, 55, 55), dtype=np.uint8)
        cac_khung.extend([khung, ke])
    return np.hstack(cac_khung)


def dinh_dang_trong_luong(chuoi_so):
    chi_so = ''.join(c for c in chuoi_so if c.isdigit())
    if len(chi_so) == 0: return '0.00'
    if len(chi_so) == 1: return f'0.0{chi_so}'
    if len(chi_so) == 2: return f'0.{chi_so}'
    return f'{chi_so[:-2]}.{chi_so[-2:]}'


def ep_trong_luong_float(gia_tri):
    if gia_tri is None:
        return None
    try:
        return float(str(gia_tri).replace(',', '.'))
    except Exception:
        return None


def ket_qua_khong_nhan_dien(nguon='none'):
    return {
        'trong_luong': '0.00',
        'trong_luong_raw': '',
        'trong_luong_float': 0.0,
        'do_tin_cay': 0.0,
        'thoi_gian_ms': 0.0,
        'nguon_nhan_dien': nguon,
    }


# ============================================================
# CAT VIEN SANG
# ============================================================

def cat_vien_sang(anh_bgr, nguong=NGUONG_VIEN_SANG, padding=PADDING_VIEN):
    gray = cv2.cvtColor(anh_bgr, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    mask_toi   = gray < nguong
    hang_co_nd = np.any(mask_toi, axis=1)
    cot_co_nd  = np.any(mask_toi, axis=0)
    if not np.any(hang_co_nd) or not np.any(cot_co_nd):
        print("  [WARN] Khong phat hien vien sang, giu nguyen")
        return anh_bgr, (0, H, 0, W)
    r0 = max(0, int(np.argmax(hang_co_nd)) - padding)
    r1 = min(H, int(H - np.argmax(hang_co_nd[::-1])) + padding)
    c0 = max(0, int(np.argmax(cot_co_nd))  - padding)
    c1 = min(W, int(W - np.argmax(cot_co_nd[::-1])) + padding)
    return anh_bgr[r0:r1, c0:c1], (r0, r1, c0, c1)


# ============================================================
# DESKEW
# ============================================================

def deskew_vung_so(anh_bgr, goc_gioi_han=GOC_DESKEW_GIOI_HAN):
    gray = cv2.cvtColor(anh_bgr, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    canh = cv2.Canny(blur, 30, 100)
    cac_duong = cv2.HoughLinesP(canh, 1, np.pi/180,
                                 threshold=max(10, W//8),
                                 minLineLength=max(8, W//10),
                                 maxLineGap=max(4, W//20))
    if cac_duong is None:
        return anh_bgr
    cac_goc = []
    for line in cac_duong:
        x1, y1, x2, y2 = line[0]
        dx, dy = x2-x1, y2-y1
        if abs(dx) < 3: continue
        g = np.degrees(np.arctan2(dy, dx))
        if abs(g) < goc_gioi_han:
            cac_goc.append(g)
    if not cac_goc:
        return anh_bgr
    goc = float(np.median(cac_goc))
    if abs(goc) < 0.3:
        return anh_bgr
    M = cv2.getRotationMatrix2D((W/2.0, H/2.0), goc, 1.0)
    print(f"  [Deskew] {goc:+.2f} do")
    return cv2.warpAffine(anh_bgr, M, (W, H),
                          flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


# ============================================================
# BO DOC (ONNX)
# ============================================================

class BoDocTrongLuong:
    def __init__(self):
        print(f"  Khoi tao ONNX: {DUONG_DAN_ONNX}")
        if not os.path.exists(DUONG_DAN_ONNX):
            raise FileNotFoundError(f"Khong tim thay model: {DUONG_DAN_ONNX}")
        if not os.path.exists(FILE_THONG_TIN):
            raise FileNotFoundError(f"Khong tim thay file class info: {FILE_THONG_TIN}")
        opt = ort.SessionOptions()
        opt.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.phien = ort.InferenceSession(DUONG_DAN_ONNX, opt,
                                          providers=['CPUExecutionProvider'])
        self.ten_dau_vao = self.phien.get_inputs()[0].name
        with open(FILE_THONG_TIN, encoding='utf-8') as f:
            thong_tin = json.load(f)
        self.cac_lop = thong_tin.get('cac_lop', thong_tin.get('classes', []))

    def tach_kenh_do(self, anh_bgr):
        hsv = cv2.cvtColor(anh_bgr, cv2.COLOR_BGR2HSV)
        lo1, hi1 = np.array([0,   80, 80]), np.array([15,  255, 255])
        lo2, hi2 = np.array([155, 80, 80]), np.array([180, 255, 255])
        mat_na = cv2.bitwise_or(cv2.inRange(hsv, lo1, hi1),
                                 cv2.inRange(hsv, lo2, hi2))
        kenh_r = anh_bgr[:, :, 2]
        return cv2.bitwise_and(kenh_r, kenh_r, mask=mat_na), mat_na

    def tim_hang_dau_tien(self, anh_bgr):
        _, mat_na = self.tach_kenh_do(anh_bgr)
        H, W = anh_bgr.shape[:2]
        kw = max(5, int(W * 0.05))
        kh = max(2, int(H * 0.005))
        hat_nhan = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, kh))
        dong_lai = cv2.morphologyEx(mat_na, cv2.MORPH_CLOSE, hat_nhan)
        duong_vien, _ = cv2.findContours(dong_lai, cv2.RETR_EXTERNAL,
                                          cv2.CHAIN_APPROX_SIMPLE)
        ds_cnt = sorted(
            [c for c in duong_vien
             if cv2.boundingRect(c)[2] >= W*0.2
             and cv2.boundingRect(c)[3] >= H*0.05],
            key=lambda c: cv2.boundingRect(c)[1]
        )
        if not ds_cnt:
            return None, None, None
        cnt  = ds_cnt[0]
        rect = cv2.minAreaRect(cnt)
        (center, size, angle) = rect
        if angle < -45:
            angle = 90 + angle
            size  = (size[1], size[0])
        M        = cv2.getRotationMatrix2D(center, angle, 1.0)
        anh_xoay = cv2.warpAffine(anh_bgr, M, (W, H), flags=cv2.INTER_CUBIC)
        tw, th   = int(size[0]), int(size[1])
        xc, yc   = int(center[0]), int(center[1])
        pad      = 5
        c0 = max(0, xc - tw//2 - pad)
        c1 = min(W, xc + tw//2 + pad)
        r0 = max(0, yc - th//2 - pad)
        r1 = min(H, yc + th//2 + pad)
        c0 = tim_bien_trai_theo_gradient(anh_xoay, c0)
        roi_bgr = anh_xoay[r0:r1, c0:c1]
        if roi_bgr.size == 0:
            return None, None, None
        return self.tach_kenh_do(roi_bgr)[0], (r0, r1), roi_bgr

    def tensor_tu_anh_32(self, rs32):
        chuan = (rs32.astype(np.float32) / 255.0 - 0.5) / 0.5
        return chuan[np.newaxis, np.newaxis, :, :]

    def xac_dinh_shear_de_thang(self, chu_sang):
        """Giong BoDocCan.xac_dinh_shear_de_thang trong Teo_nua.py."""
        H, W  = chu_sang.shape
        H_s   = max(20, H // 2)
        W_s   = max(20, W // 2)
        anh_s = cv2.resize(chu_sang, (W_s, H_s), interpolation=cv2.INTER_AREA)

        best_score, best_sf = -1, 0
        for i in range(-50, 50, 4):
            sf      = i / 100.0
            M       = np.float32([[1, sf, -sf * H_s / 2.0], [0, 1, 0]])
            sheared = cv2.warpAffine(anh_s, M, (W_s, H_s), flags=cv2.INTER_NEAREST)
            score   = np.var(np.sum(sheared > 128, axis=0))
            if score > best_score:
                best_score, best_sf = score, sf

        best_sf_ft = best_sf
        for i in range(-5, 6):
            sf      = best_sf + i / 100.0
            M       = np.float32([[1, sf, -sf * H_s / 2.0], [0, 1, 0]])
            sheared = cv2.warpAffine(anh_s, M, (W_s, H_s), flags=cv2.INTER_NEAREST)
            score   = np.var(np.sum(sheared > 128, axis=0))
            if score > best_score:
                best_score, best_sf_ft = score, sf
        return best_sf_ft

    def du_doan_ky_tu(self, anh_xam_uint8):
        """anh_xam_uint8: crop sau tien_xu_ly Teo (LED sang tren nen toi), giong Teo_nua."""
        rs32    = bien_doi_khu_bloom(anh_xam_uint8)
        dau_vao = self.tensor_tu_anh_32(rs32).astype(np.float32)
        dau_ra  = self.phien.run(None, {self.ten_dau_vao: dau_vao})[0]
        xac_suat = tinh_softmax(dau_ra[0])
        order    = np.argsort(-xac_suat)
        chi_so   = int(order[0])
        ten_lop  = self.cac_lop[chi_so]
        conf     = float(xac_suat[chi_so])
        ky_tu    = MAP_LOP_KY_TU.get(ten_lop, ten_lop)
        if ten_lop == "8" and conf < 0.62 and len(order) > 1:
            i1 = int(order[1])
            if self.cac_lop[i1] == "0" and float(xac_suat[i1]) > 0.15:
                ky_tu = MAP_LOP_KY_TU.get("0", "0")
                conf  = float(xac_suat[i1])
        return ky_tu, conf, rs32


# ============================================================
# TIEN XU LY O - tach LED do, kiem tra blank
# ============================================================

def tien_xu_ly_o(o_bgr):
    """
    Tach LED do tu o BGR.
    Tra ve (gray_led, co_noi_dung).

    gray_led    : anh xam, pixel sang = LED bat, nen = 0
                  (CHUA nhi phan - bien_doi_khu_bloom xu ly tiep)
    co_noi_dung : True neu phan bo pixel sang du lon de la ky tu that.
                  False neu chi la bloom/nhieu vach mep.

    Phan biet LED that vs bloom tu o ke:
      Bloom : chi 1-2 cot sat vien, ty_le_cot < 25% chieu rong o
      LED   : phan bo >= 25% chieu rong VA >= 35% chieu cao
    """
    if o_bgr is None or o_bgr.size == 0:
        return np.zeros((8, 8), dtype=np.uint8), False

    H_o, W_o = o_bgr.shape[:2]

    # --- Lay kenh do (LED do sang) ---
    hsv = cv2.cvtColor(o_bgr, cv2.COLOR_BGR2HSV)
    lo1 = np.array([0,   50, 80]);  hi1 = np.array([15,  255, 255])
    lo2 = np.array([155, 50, 80]);  hi2 = np.array([180, 255, 255])
    mask_do = cv2.bitwise_or(cv2.inRange(hsv, lo1, hi1),
                              cv2.inRange(hsv, lo2, hi2))
    kenh_r  = o_bgr[:, :, 2]
    gray    = cv2.bitwise_and(kenh_r, kenh_r, mask=mask_do)
    # gray: pixel sang (>0) = vung LED do, nen = 0

    # --- Kiem tra co du pixel LED khong ---
    px_sang = gray[gray > 30]
    if len(px_sang) < 10:
        return gray, False

    # --- Nhi phan hoa de phan tich phan bo ---
    nguong_thr = max(30.0, float(np.percentile(px_sang, 40)))
    _, binary  = cv2.threshold(gray, nguong_thr, 255, cv2.THRESH_BINARY)

    # --- Kiem tra phan bo 2 chieu ---
    proj_cot  = np.sum(binary > 0, axis=0)            # (W_o,)
    proj_hang = np.sum(binary > 0, axis=1)             # (H_o,)
    ty_le_cot  = np.sum(proj_cot  > H_o * 0.10) / max(1, W_o)
    ty_le_hang = np.sum(proj_hang > W_o * 0.05) / max(1, H_o)

    # LED that: >= 25% rong VA >= 35% cao
    co_noi_dung = (ty_le_cot >= 0.25 and ty_le_hang >= 0.35)

    return gray, co_noi_dung


_BO_DOC_LOCK = threading.Lock()
_BO_DOC_CACHE = None
_YOLO_LOCK = threading.Lock()
_YOLO_CACHE = None
_YOLO_UNAVAILABLE = False


def lay_bo_doc_trong_luong():
    """Khoi tao ONNX mot lan, dung lai cho MQTT va nhan dien truc tuyen."""
    global _BO_DOC_CACHE
    with _BO_DOC_LOCK:
        if _BO_DOC_CACHE is None:
            _BO_DOC_CACHE = BoDocTrongLuong()
        return _BO_DOC_CACHE


def lay_yolo_trong_luong():
    """Load YOLO cuc bo neu co weights; khong tai model tu internet."""
    global _YOLO_CACHE, _YOLO_UNAVAILABLE
    if _YOLO_UNAVAILABLE:
        return None
    with _YOLO_LOCK:
        if _YOLO_CACHE is not None:
            return _YOLO_CACHE
        if not DUONG_DAN_YOLO or not os.path.exists(DUONG_DAN_YOLO):
            _YOLO_UNAVAILABLE = True
            return None
        try:
            from ultralytics import YOLO
            _YOLO_CACHE = YOLO(DUONG_DAN_YOLO)
            return _YOLO_CACHE
        except Exception as exc:
            print(f"  [WARN] Khong load duoc YOLO: {exc}")
            _YOLO_UNAVAILABLE = True
            return None


def _ghi_debug(thu_muc_debug, ten_file, anh):
    if not thu_muc_debug or anh is None:
        return
    os.makedirs(thu_muc_debug, exist_ok=True)
    cv2.imwrite(os.path.join(thu_muc_debug, ten_file), anh)


def _nhan_tu_lop_yolo(label):
    label = str(label).strip()
    lower = label.lower()
    if lower in ('comma', 'phay', ','):
        return '.'
    if lower in ('dot', 'point', 'decimal', '.'):
        return '.'
    return MAP_LOP_KY_TU.get(label, label)


def _mask_led_do(anh_bgr):
    hsv = cv2.cvtColor(anh_bgr, cv2.COLOR_BGR2HSV)
    lo1 = np.array([0, 45, 100]); hi1 = np.array([18, 255, 255])
    lo2 = np.array([155, 45, 100]); hi2 = np.array([180, 255, 255])
    mask_hsv = cv2.bitwise_or(cv2.inRange(hsv, lo1, hi1), cv2.inRange(hsv, lo2, hi2))

    b, g, r = cv2.split(anh_bgr)
    mask_rgb = (
        (r.astype(np.int16) > 120) &
        (r.astype(np.int16) > g.astype(np.int16) + 25) &
        (r.astype(np.int16) > b.astype(np.int16) + 25)
    ).astype(np.uint8) * 255

    mask = cv2.bitwise_or(mask_hsv, mask_rgb)
    mask = cv2.medianBlur(mask, 3)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    return mask


def _mask_led_sang(anh_bgr, nguong_r=250, nguong_g=180):
    b, g, r = cv2.split(anh_bgr)
    mask = (
        (r.astype(np.int16) >= nguong_r) &
        (g.astype(np.int16) >= nguong_g) &
        (r.astype(np.int16) >= b.astype(np.int16) + 15)
    ).astype(np.uint8) * 255
    mask = cv2.medianBlur(mask, 3)
    return mask


def _merge_runs(indices, max_gap):
    if len(indices) == 0:
        return []
    runs = []
    start = int(indices[0])
    prev = int(indices[0])
    for value in indices[1:]:
        value = int(value)
        if value - prev <= max_gap:
            prev = value
            continue
        runs.append((start, prev + 1))
        start = value
        prev = value
    runs.append((start, prev + 1))
    return runs


def _segment_score(mask, x0, x1, y0, y1):
    H, W = mask.shape[:2]
    x0 = max(0, min(W - 1, int(round(x0))))
    x1 = max(x0 + 1, min(W, int(round(x1))))
    y0 = max(0, min(H - 1, int(round(y0))))
    y1 = max(y0 + 1, min(H, int(round(y1))))
    roi = mask[y0:y1, x0:x1]
    if roi.size == 0:
        return 0.0
    return float(np.mean(roi > 0))


def _segment_score_max(mask, boxes):
    return max((_segment_score(mask, *box) for box in boxes), default=0.0)


def _doc_so_7_doan(mask_digit):
    H, W = mask_digit.shape[:2]
    if H < 8 or W < 3:
        return None, 0.0

    # So 1 tren LED 7 doan thuong rat hep, tranh ep vao layout 7 doan day du.
    if W / max(1, H) < 0.42:
        top_score = _segment_score_max(mask_digit, (
            (W * 0.10, W * 0.90, H * 0.00, H * 0.22),
            (W * 0.10, W * 0.90, H * 0.28, H * 0.46),
        ))
        right_top = _segment_score(mask_digit, W * 0.68, W * 1.00, H * 0.14, H * 0.44)
        right_bottom = _segment_score(mask_digit, W * 0.68, W * 1.00, H * 0.54, H * 0.88)
        left_top = _segment_score(mask_digit, W * 0.00, W * 0.28, H * 0.14, H * 0.44)
        left_bottom = _segment_score(mask_digit, W * 0.00, W * 0.28, H * 0.54, H * 0.88)
        if top_score >= 0.14 and right_bottom >= 0.18 and left_bottom < 0.12:
            return '7', max(0.60, min(0.96, float(np.mean([top_score, right_top, right_bottom]) * 2.0)))
        if right_bottom >= 0.48 and left_bottom < 0.08 and top_score >= 0.12 and left_top < 0.28:
            return '7', max(0.60, min(0.94, float((right_bottom + right_top + top_score) / 3.0 * 1.8)))
        return '1', 0.90

    scores = {
        'a': _segment_score_max(mask_digit, (
            (W * 0.18, W * 0.82, H * 0.00, H * 0.16),
            (W * 0.18, W * 0.82, H * 0.04, H * 0.20),
        )),
        'b': _segment_score(mask_digit, W * 0.76, W * 1.00, H * 0.18, H * 0.40),
        'c': _segment_score(mask_digit, W * 0.76, W * 1.00, H * 0.60, H * 0.82),
        'd': _segment_score_max(mask_digit, (
            (W * 0.18, W * 0.82, H * 0.78, H * 0.94),
            (W * 0.18, W * 0.82, H * 0.84, H * 1.00),
        )),
        'e': _segment_score(mask_digit, W * 0.00, W * 0.24, H * 0.60, H * 0.82),
        'f': _segment_score(mask_digit, W * 0.00, W * 0.24, H * 0.18, H * 0.40),
        'g': _segment_score_max(mask_digit, (
            (W * 0.18, W * 0.82, H * 0.34, H * 0.48),
            (W * 0.18, W * 0.82, H * 0.42, H * 0.56),
            (W * 0.18, W * 0.82, H * 0.50, H * 0.64),
        )),
    }

    if (
        scores['e'] < 0.12 and scores['f'] < 0.12 and scores['d'] < 0.23
        and scores['a'] >= 0.16 and scores['b'] >= 0.16 and scores['c'] >= 0.14
    ):
        return '7', max(0.55, min(0.98, float(np.mean([scores['a'], scores['b'], scores['c']]) * 2.2)))

    if (
        scores['c'] >= 0.50 and scores['e'] < 0.10 and scores['d'] < 0.24
        and scores['b'] >= 0.15 and scores['f'] < 0.28
    ):
        return '7', max(0.55, min(0.95, float(np.mean([scores['b'], scores['c'], scores['g']]) * 1.7)))

    if (
        scores['e'] < 0.12 and scores['d'] < 0.24
        and scores['b'] >= 0.16 and scores['c'] >= 0.16
        and scores['f'] >= 0.20 and scores['g'] >= 0.20
    ):
        return '4', max(0.55, min(0.98, float(np.mean([scores['b'], scores['c'], scores['f'], scores['g']]) * 2.0)))

    active = {key for key, value in scores.items() if value >= 0.16}

    patterns = {
        '0': set('abcdef'),
        '1': set('bc'),
        '2': set('abdeg'),
        '3': set('abcdg'),
        '4': set('bcfg'),
        '5': set('acdfg'),
        '6': set('acdefg'),
        '7': set('abc'),
        '8': set('abcdefg'),
        '9': set('abcdfg'),
    }

    best_digit = None
    best_dist = 99
    for digit, pattern in patterns.items():
        dist = len(active.symmetric_difference(pattern))
        if dist < best_dist:
            best_digit = digit
            best_dist = dist

    if best_digit is None or best_dist > 3:
        return None, 0.0

    matched = patterns[best_digit]
    avg_score = float(np.mean([scores[key] for key in matched])) if matched else 0.0
    confidence = max(0.0, min(1.0, (1.0 - best_dist / 7.0) * 0.7 + min(avg_score * 2.0, 1.0) * 0.3))
    return best_digit, confidence


def _cat_hang_led_tren(anh_bgr, mask):
    H, W = mask.shape[:2]
    row_sum = np.sum(mask > 0, axis=1)
    active_rows = np.where(row_sum >= max(3, int(W * 0.012)))[0]
    runs = _merge_runs(active_rows, max(2, int(H * 0.035)))
    candidates = []
    for y0, y1 in runs:
        band = mask[y0:y1, :]
        area = int(np.sum(band > 0))
        if (y1 - y0) >= max(12, int(H * 0.06)) and area >= 80:
            candidates.append((y0, y1, area))
    if not candidates:
        return None, None

    # Chon hang LED do dau tien: trong anh mau la "Trong Luong (kg)".
    y0, y1, _ = sorted(candidates, key=lambda item: item[0])[0]
    pad_y = max(5, int((y1 - y0) * 0.20))
    y0 = max(0, y0 - pad_y)
    y1 = min(H, y1 + pad_y)

    band = mask[y0:y1, :]
    col_sum = np.sum(band > 0, axis=0)
    active_cols = np.where(col_sum >= max(2, int((y1 - y0) * 0.035)))[0]
    if len(active_cols) == 0:
        return None, None

    x0 = max(0, int(active_cols.min()) - 8)
    x1 = min(W, int(active_cols.max()) + 9)
    return anh_bgr[y0:y1, x0:x1], mask[y0:y1, x0:x1]


def _tach_chu_so_led_tu_mask(hang_mask):
    H, W = hang_mask.shape[:2]
    col_sum = np.sum(hang_mask > 0, axis=0)
    active_cols = np.where(col_sum >= max(1, int(H * 0.025)))[0]
    runs = _merge_runs(active_cols, 1)
    if not runs:
        return [], []

    digits = []
    confs = []
    for x0, x1 in runs:
        run_mask = hang_mask[:, x0:x1]
        ys, xs = np.where(run_mask > 0)
        if len(xs) < 8:
            continue

        bx0 = max(0, int(xs.min()) + x0 - 3)
        bx1 = min(W, int(xs.max()) + x0 + 4)
        by0 = max(0, int(ys.min()) - 3)
        by1 = min(H, int(ys.max()) + 4)
        bw = bx1 - bx0
        bh = by1 - by0
        area = int(np.sum(hang_mask[by0:by1, bx0:bx1] > 0))

        # Dau cham thap phan nho va nam thap; bo qua vi dinh_dang_trong_luong()
        # luon chen dau cham truoc 2 chu so cuoi.
        if bh < H * 0.42 and by0 > H * 0.38:
            continue
        if bw < H * 0.10 and bh < H * 0.45 and area < 140:
            continue

        digit, conf = _doc_so_7_doan(hang_mask[by0:by1, bx0:bx1])
        if digit is None:
            continue
        digits.append(digit)
        confs.append(conf)

    return digits, confs


def _tach_chu_so_led_theo_o(hang_mask):
    H, W = hang_mask.shape[:2]
    col_sum = np.sum(hang_mask > 0, axis=0)
    active_cols = np.where(col_sum >= max(1, int(H * 0.025)))[0]
    runs = _merge_runs(active_cols, 1)
    if not runs:
        return [], []

    sig_boxes = []
    for x0, x1 in runs:
        run_mask = hang_mask[:, x0:x1]
        ys, xs = np.where(run_mask > 0)
        if len(xs) < 8:
            continue

        bx0 = max(0, int(xs.min()) + x0 - 3)
        bx1 = min(W, int(xs.max()) + x0 + 4)
        by0 = max(0, int(ys.min()) - 3)
        by1 = min(H, int(ys.max()) + 4)
        bw = bx1 - bx0
        area = int(np.sum(hang_mask[by0:by1, bx0:bx1] > 0))

        if bw < max(14, int(H * 0.10)) or area < 120:
            continue
        if bw < max(18, int(H * 0.14)) and (bx0 < W * 0.12 or bx1 > W * 0.95):
            continue
        sig_boxes.append((bx0, bx1, by0, by1))

    if not sig_boxes:
        return [], []

    x0 = min(box[0] for box in sig_boxes)
    x1 = max(box[1] for box in sig_boxes)
    y0 = max(0, min(box[2] for box in sig_boxes) - 2)
    y1 = min(H, max(box[3] for box in sig_boxes) + 2)
    width = x1 - x0
    if width <= 0 or y1 <= y0:
        return [], []

    pitch = max(38.0, min(64.0, H * 0.32))
    n_digits = int(round(width / pitch))
    n_digits = max(1, min(5, n_digits))
    n_digits = max(n_digits, min(len(sig_boxes), 5))

    digits = []
    confs = []
    for idx in range(n_digits):
        cell_x0 = int(round(x0 + idx * width / n_digits))
        cell_x1 = int(round(x0 + (idx + 1) * width / n_digits))
        pad_x = max(1, int((cell_x1 - cell_x0) * 0.05))
        cell_x0 = max(0, cell_x0 - pad_x)
        cell_x1 = min(W, cell_x1 + pad_x)
        cell = hang_mask[y0:y1, cell_x0:cell_x1]

        ys, xs = np.where(cell > 0)
        if len(xs) < 8:
            return [], []

        bx0 = max(0, int(xs.min()) - 2)
        bx1 = min(cell.shape[1], int(xs.max()) + 3)
        by0 = max(0, int(ys.min()) - 2)
        by1 = min(cell.shape[0], int(ys.max()) + 3)
        digit, conf = _doc_so_7_doan(cell[by0:by1, bx0:bx1])
        if digit is None:
            return [], []
        digits.append(digit)
        confs.append(conf)

    return digits, confs


def _doc_tam_o_hien_thi():
    try:
        centers = [
            float(item.strip())
            for item in TAM_O_HIEN_THI_TY_LE.split(',')
            if item.strip()
        ]
    except Exception:
        centers = []

    so_o = max(1, SO_O_HIEN_THI_CO_DINH)
    if len(centers) < so_o:
        centers = [(idx + 0.5) / so_o for idx in range(so_o)]
    return centers[:so_o]


def _doc_do_rong_o_hien_thi():
    so_o = max(1, SO_O_HIEN_THI_CO_DINH)
    try:
        widths = [
            float(item.strip())
            for item in O_HIEN_THI_W_TY_LE_CHUOI.split(',')
            if item.strip()
        ]
    except Exception:
        widths = []

    if len(widths) < so_o:
        widths.extend([O_HIEN_THI_W_TY_LE] * (so_o - len(widths)))
    return widths[:so_o]


def _cat_o_hien_thi_co_dinh(roi_bgr):
    H, W = roi_bgr.shape[:2]
    y0 = int(round(H * O_HIEN_THI_Y0_TY_LE))
    y1 = int(round(H * O_HIEN_THI_Y1_TY_LE))
    y0 = max(0, min(y0, H - 2))
    y1 = max(y0 + 1, min(y1, H))

    slots = []
    widths = _doc_do_rong_o_hien_thi()
    for idx, center in enumerate(_doc_tam_o_hien_thi()):
        half_w = widths[idx] / 2.0 if idx < len(widths) else O_HIEN_THI_W_TY_LE / 2.0
        x0 = int(round(W * (center - half_w)))
        x1 = int(round(W * (center + half_w)))
        x0 = max(0, min(x0, W - 2))
        x1 = max(x0 + 1, min(x1, W))
        slots.append({
            'index': idx,
            'anh': roi_bgr[y0:y1, x0:x1],
            'bbox': (x0, y0, x1, y1),
        })
    return slots


def _chuan_hoa_ky_tu_so(ky_tu):
    digits = ''.join(ch for ch in str(ky_tu) if ch.isdigit())
    return digits[:1] if digits else ''


def _crop_theo_mask_sang(anh_xam, mask=None, pad=4, nguong=30, percentile=40):
    if anh_xam is None or anh_xam.size == 0:
        return np.zeros((8, 8), dtype=np.uint8), False
    if anh_xam.ndim == 3:
        anh_xam = cv2.cvtColor(anh_xam, cv2.COLOR_BGR2GRAY)

    if mask is None:
        diem_sang = anh_xam[anh_xam > nguong]
        if len(diem_sang) < 8:
            return anh_xam, False
        nguong_cat = max(float(nguong), float(np.percentile(diem_sang, percentile)))
        mask = (anh_xam >= nguong_cat).astype(np.uint8) * 255

    ys, xs = np.where(mask > 0)
    if len(xs) < 8:
        return anh_xam, False

    x0 = max(0, int(xs.min()) - pad)
    x1 = min(anh_xam.shape[1], int(xs.max()) + pad + 1)
    y0 = max(0, int(ys.min()) - pad)
    y1 = min(anh_xam.shape[0], int(ys.max()) + pad + 1)
    return anh_xam[y0:y1, x0:x1], True


def _du_doan_so_onnx(bo_doc, anh_xam, mask=None, nguong=30, percentile=40):
    if bo_doc is None:
        return '', 0.0
    crop, ok = _crop_theo_mask_sang(
        anh_xam,
        mask=mask,
        nguong=nguong,
        percentile=percentile,
    )
    if not ok:
        return '', 0.0
    try:
        ky_tu, conf, _ = bo_doc.du_doan_ky_tu(crop)
    except Exception:
        return '', 0.0
    return _chuan_hoa_ky_tu_so(ky_tu), float(conf)


def _kenh_do_hsv_mem(anh_bgr):
    hsv = cv2.cvtColor(anh_bgr, cv2.COLOR_BGR2HSV)
    lo1 = np.array([0, 40, 60])
    hi1 = np.array([18, 255, 255])
    lo2 = np.array([150, 40, 60])
    hi2 = np.array([180, 255, 255])
    mask = cv2.bitwise_or(cv2.inRange(hsv, lo1, hi1), cv2.inRange(hsv, lo2, hi2))
    kenh_r = anh_bgr[:, :, 2]
    return cv2.bitwise_and(kenh_r, kenh_r, mask=mask)


def _slot_dau_la_so_mot(mask_sang):
    ys, xs = np.where(mask_sang > 0)
    if len(xs) < O_HIEN_THI_MIN_LED_PIX:
        return False, 0.0

    x0 = max(0, int(xs.min()) - 3)
    x1 = min(mask_sang.shape[1], int(xs.max()) + 4)
    y0 = max(0, int(ys.min()) - 3)
    y1 = min(mask_sang.shape[0], int(ys.max()) + 4)
    crop = mask_sang[y0:y1, x0:x1]
    H, W = crop.shape[:2]
    if H < 12 or W < 4:
        return False, 0.0

    ty_le = W / max(1, H)
    diem_a = _segment_score_max(crop, (
        (W * 0.18, W * 0.82, H * 0.00, H * 0.16),
        (W * 0.18, W * 0.82, H * 0.04, H * 0.20),
    ))
    diem_g = _segment_score_max(crop, (
        (W * 0.18, W * 0.82, H * 0.34, H * 0.48),
        (W * 0.18, W * 0.82, H * 0.42, H * 0.56),
        (W * 0.18, W * 0.82, H * 0.50, H * 0.64),
    ))
    cot_sang = np.sum(crop > 0, axis=0)
    hang_sang = np.sum(crop > 0, axis=1)
    ty_le_cot = float(np.mean(cot_sang >= max(1, int(H * 0.08))))
    ty_le_hang = float(np.mean(hang_sang >= max(1, int(W * 0.08))))

    la_so_1 = (
        ty_le <= 0.52
        and diem_a < 0.56
        and diem_g < 0.12
        and ty_le_cot <= 0.68
        and ty_le_hang >= 0.45
    )
    conf = max(0.72, min(0.95, (0.52 - min(ty_le, 0.52)) * 1.2 + (0.12 - min(diem_g, 0.12)) * 1.5 + 0.72))
    return la_so_1, conf


def _doc_o_hien_thi_co_dinh(o_bgr, bo_doc=None, chi_so_o=None):
    mask_sang = _mask_led_sang(o_bgr, nguong_r=220, nguong_g=115)
    so_pixel_sang = int(np.sum(mask_sang > 0))
    if so_pixel_sang < O_HIEN_THI_MIN_LED_PIX:
        return '', 0.0, 'blank', {'pixel_sang': so_pixel_sang}

    digit_mask, conf_mask = _du_doan_so_onnx(bo_doc, mask_sang, mask_sang)

    digit_red, conf_red = _du_doan_so_onnx(
        bo_doc,
        o_bgr[:, :, 2],
        mask_sang,
        nguong=80,
    )
    digit_red2, conf_red2 = _du_doan_so_onnx(
        bo_doc,
        o_bgr[:, :, 2],
        None,
        nguong=80,
    )
    if conf_red2 > conf_red:
        digit_red, conf_red = digit_red2, conf_red2

    digit_hsv = ''
    conf_hsv = 0.0
    kenh_hsv = _kenh_do_hsv_mem(o_bgr)
    for percentile in (25, 40, 60, 75):
        digit_tmp, conf_tmp = _du_doan_so_onnx(
            bo_doc,
            kenh_hsv,
            None,
            nguong=30,
            percentile=percentile,
        )
        if conf_tmp > conf_hsv:
            digit_hsv, conf_hsv = digit_tmp, conf_tmp

    digit_rule = ''
    conf_rule = 0.0
    ys, xs = np.where(mask_sang > 0)
    if len(xs) >= 8:
        x0 = max(0, int(xs.min()) - 3)
        x1 = min(mask_sang.shape[1], int(xs.max()) + 4)
        y0 = max(0, int(ys.min()) - 3)
        y1 = min(mask_sang.shape[0], int(ys.max()) + 4)
        digit_tmp, conf_tmp = _doc_so_7_doan(mask_sang[y0:y1, x0:x1])
        digit_rule = digit_tmp or ''
        conf_rule = float(conf_tmp)

    digit_chon = digit_mask
    conf_chon = conf_mask
    nguon = 'mask'

    la_so_1_slot_dau, conf_so_1_slot_dau = (
        _slot_dau_la_so_mot(mask_sang) if chi_so_o == 0 else (False, 0.0)
    )

    # Neu kenh do/HSV cung thay so 6 ro, khong de rule hinh hoc hep ep thanh 1.
    if la_so_1_slot_dau:
        digit_chon, conf_chon, nguon = '1', conf_so_1_slot_dau, 'slot1_rule'
    elif digit_red == '6' and digit_hsv == '6' and conf_red >= 0.60 and conf_hsv >= 0.70:
        digit_chon, conf_chon, nguon = digit_hsv, conf_hsv, 'hsv6'
    # Mot so "1" va "0" rat hep, ONNX de nham sang 7/2 khi anh bi choi.
    elif (
        digit_rule in ('0', '1')
        and conf_rule >= 0.80
        and conf_mask < 0.65
        and (conf_red < 0.70 or digit_red == digit_rule)
    ):
        digit_chon, conf_chon, nguon = digit_rule, conf_rule, 'rule01'
    elif digit_red == '6' and digit_mask == '5' and conf_red >= 0.65:
        digit_chon, conf_chon, nguon = digit_red, conf_red, 'red6'
    elif digit_hsv == '8' and conf_hsv >= 0.38 and digit_mask == '9' and conf_mask < 0.45 and conf_red < 0.50:
        digit_chon, conf_chon, nguon = digit_hsv, conf_hsv, 'hsv8'
    elif digit_rule and conf_rule >= 0.90 and conf_mask < 0.35 and conf_red < 0.65:
        digit_chon, conf_chon, nguon = digit_rule, conf_rule, 'rulehi'
    elif digit_red and conf_red >= 0.65 and conf_red >= conf_mask + 0.03:
        digit_chon, conf_chon, nguon = digit_red, conf_red, 'red'
    elif digit_mask and conf_mask >= 0.25:
        digit_chon, conf_chon, nguon = digit_mask, conf_mask, 'mask'
    elif digit_hsv and conf_hsv >= 0.40 and conf_hsv >= conf_red + 0.05:
        digit_chon, conf_chon, nguon = digit_hsv, conf_hsv, 'hsv'
    elif digit_red and conf_red >= 0.25:
        digit_chon, conf_chon, nguon = digit_red, conf_red, 'redlo'
    elif digit_rule:
        digit_chon, conf_chon, nguon = digit_rule, conf_rule, 'rule'

    return digit_chon, float(conf_chon), nguon, {
        'pixel_sang': so_pixel_sang,
        'mask': (digit_mask, conf_mask),
        'red': (digit_red, conf_red),
        'hsv': (digit_hsv, conf_hsv),
        'rule': (digit_rule, conf_rule),
        'slot1_la_1': (la_so_1_slot_dau, conf_so_1_slot_dau),
    }


def _nhan_dien_5_o_co_dinh(roi_hien_thi, thu_muc_debug=None, bo_doc=None):
    slots = _cat_o_hien_thi_co_dinh(roi_hien_thi)
    if not slots:
        return None

    digits = []
    confs = []
    thong_tin_o = []
    debug = roi_hien_thi.copy()

    for slot in slots:
        digit, conf, nguon, thong_tin = _doc_o_hien_thi_co_dinh(
            slot['anh'],
            bo_doc=bo_doc,
            chi_so_o=slot['index'],
        )
        thong_tin_o.append((slot, digit, conf, nguon, thong_tin))
        x0, y0, x1, y1 = slot['bbox']
        mau = (0, 220, 80) if digit else (80, 80, 80)
        cv2.rectangle(debug, (x0, y0), (x1 - 1, y1 - 1), mau, 1)
        nhan = digit if digit else '_'
        cv2.putText(
            debug,
            f"{slot['index'] + 1}:{nhan}",
            (x0 + 2, max(14, y0 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            mau,
            1,
            cv2.LINE_AA,
        )
        if digit:
            digits.append(digit)
            confs.append(conf)

    raw_digits = ''.join(digits)
    if not raw_digits:
        return None

    trong_luong = dinh_dang_trong_luong(raw_digits)
    trong_luong_float = ep_trong_luong_float(trong_luong)
    if trong_luong_float is None or trong_luong_float > 999.95:
        return None

    _ghi_debug(thu_muc_debug, "led5_01_display_roi.jpg", roi_hien_thi)
    _ghi_debug(thu_muc_debug, "led5_02_slots.jpg", debug)
    _ghi_debug(thu_muc_debug, "led5_03_mask_220_115.jpg", _mask_led_sang(roi_hien_thi, 220, 115))

    return {
        'digits': digits,
        'confs': confs,
        'debug': debug,
        'thong_tin_o': thong_tin_o,
        'nguon': 'led7_fixed5',
    }


def nhan_dien_led_7_doan_tu_bgr(anh_goc, thu_muc_debug=None, bo_doc=None):
    """Nhan dien truc tiep LED 7 doan mau do, toi uu cho man hinh can trong anh mau."""
    if anh_goc is None or anh_goc.size == 0:
        return None

    t0 = time.perf_counter()
    ung_vien = []

    roi_hien_thi, _ = cat_roi_hien_thi_trong_luong(anh_goc)
    bo_doc_slot = bo_doc
    if bo_doc_slot is None:
        try:
            bo_doc_slot = lay_bo_doc_trong_luong()
        except Exception as exc:
            print(f"  [WARN] ONNX fixed-slot loi: {exc}")

    ket_qua_5_o = _nhan_dien_5_o_co_dinh(
        roi_hien_thi,
        thu_muc_debug=thu_muc_debug,
        bo_doc=bo_doc_slot,
    )
    if ket_qua_5_o:
        ung_vien.append((
            ket_qua_5_o['digits'],
            ket_qua_5_o['confs'],
            ket_qua_5_o['nguon'],
            ket_qua_5_o['debug'],
            -1,
        ))

    for muc_uu_tien, (nguong_r, nguong_g) in enumerate(((250, 180), (245, 165), (240, 155), (230, 130))):
        mask_sang = _mask_led_sang(roi_hien_thi, nguong_r=nguong_r, nguong_g=nguong_g)
        digits, confs = _tach_chu_so_led_tu_mask(mask_sang)
        if digits:
            ung_vien.append((digits, confs, f"led7_display_{nguong_r}_{nguong_g}", mask_sang, muc_uu_tien))
        digits_o, confs_o = _tach_chu_so_led_theo_o(mask_sang)
        if digits_o:
            ung_vien.append((digits_o, confs_o, f"led7_cells_{nguong_r}_{nguong_g}", mask_sang, muc_uu_tien))

    mask_sang_mem = _mask_led_sang(roi_hien_thi, nguong_r=220, nguong_g=115)
    digits_o, confs_o = _tach_chu_so_led_theo_o(mask_sang_mem)
    if digits_o:
        ung_vien.append((digits_o, confs_o, "led7_cells_220_115", mask_sang_mem, 4))

    anh_roi, _ = cat_roi_co_dinh_goc_phai_duoi(anh_goc)
    mask_do = _mask_led_do(anh_roi)
    _, hang_mask = _cat_hang_led_tren(anh_roi, mask_do)
    if hang_mask is not None:
        digits, confs = _tach_chu_so_led_tu_mask(hang_mask)
        if digits:
            ung_vien.append((digits, confs, "led7_roi_do", hang_mask, 5))

    if not ung_vien:
        return None

    def diem_ung_vien(item):
        digits, confs, _, _, muc_uu_tien = item
        conf_tb = float(np.mean(confs)) if confs else 0.0
        # Khi da co crop man hinh on dinh, ket qua 5 o co dinh duoc uu tien
        # de tranh blob bi choi sang lam doan nham so chu so.
        return int(muc_uu_tien < 0), min(len(digits), 5), int(conf_tb >= 0.70), -muc_uu_tien, conf_tb

    digits, confs, nguon, mask_debug, _ = max(ung_vien, key=diem_ung_vien)
    _ghi_debug(thu_muc_debug, "led7_01_display_roi.jpg", roi_hien_thi)
    _ghi_debug(thu_muc_debug, "led7_02_mask_chon.jpg", mask_debug)

    raw_digits = ''.join(digits)
    trong_luong = dinh_dang_trong_luong(raw_digits)
    return {
        'trong_luong': trong_luong,
        'trong_luong_raw': raw_digits,
        'trong_luong_float': ep_trong_luong_float(trong_luong),
        'do_tin_cay': float(np.mean(confs)) if confs else 0.0,
        'thoi_gian_ms': round((time.perf_counter() - t0) * 1000, 2),
        'nguon_nhan_dien': nguon,
    }


def nhan_dien_trong_luong_yolo_tu_bgr(anh_goc, thu_muc_debug=None, model=None):
    """
    Nhan dien bang YOLO neu co weights local.
    Yeu cau class la cac ky tu so/dot/comma, sort theo toa do x roi ghep chuoi.
    """
    if anh_goc is None or anh_goc.size == 0:
        return None

    model = model or lay_yolo_trong_luong()
    if model is None:
        return None

    t0 = time.perf_counter()
    try:
        results = model.predict(anh_goc, conf=YOLO_CONF, verbose=False)
    except Exception as exc:
        print(f"  [WARN] YOLO predict loi: {exc}")
        return None

    if not results:
        return None

    result = results[0]
    boxes = getattr(result, 'boxes', None)
    if boxes is None or len(boxes) == 0:
        return None

    names = getattr(result, 'names', None) or getattr(model, 'names', {})
    ky_tu = []
    for box in boxes:
        try:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].detach().cpu().numpy().tolist()
        except Exception:
            continue
        label = names.get(cls_id, str(cls_id)) if isinstance(names, dict) else str(cls_id)
        char = _nhan_tu_lop_yolo(label)
        if char in ('blank', ''):
            continue
        x_center = (float(xyxy[0]) + float(xyxy[2])) / 2.0
        ky_tu.append((x_center, char, conf))

    if not ky_tu:
        return None

    ky_tu.sort(key=lambda item: item[0])
    raw = ''.join(item[1] for item in ky_tu)
    digits = ''.join(ch for ch in raw if ch.isdigit())
    if not digits:
        return None

    trong_luong = dinh_dang_trong_luong(digits)
    return {
        'trong_luong': trong_luong,
        'trong_luong_raw': raw,
        'trong_luong_float': ep_trong_luong_float(trong_luong),
        'do_tin_cay': float(np.mean([item[2] for item in ky_tu])),
        'thoi_gian_ms': round((time.perf_counter() - t0) * 1000, 2),
        'nguon_nhan_dien': 'yolo',
    }


def nhan_dien_trong_luong_onnx_tu_bgr(anh_goc, thu_muc_debug=None, bo_doc=None):
    """
    Nhan dien so can tu anh BGR bang model ONNX cuc bo.
    Tra ve dict co trong_luong_text va trong_luong_float, khong goi API chat.
    """
    if anh_goc is None or anh_goc.size == 0:
        return None

    bo_doc = bo_doc or lay_bo_doc_trong_luong()
    t0 = time.perf_counter()

    _ghi_debug(thu_muc_debug, "buoc_01_goc.jpg", anh_goc)

    anh_bgr, _ = cat_roi_co_dinh_goc_phai_duoi(anh_goc)
    _ghi_debug(thu_muc_debug, "buoc_02_roi_goc_phai_duoi.jpg", anh_bgr)

    _, _, roi_bgr = bo_doc.tim_hang_dau_tien(anh_bgr)
    if roi_bgr is None:
        return None
    _ghi_debug(thu_muc_debug, "buoc_03_hang1_crop.jpg", roi_bgr)

    vung_so, _ = cat_vien_sang(
        roi_bgr,
        nguong=NGUONG_VIEN_SANG,
        padding=PADDING_VIEN,
    )
    if vung_so is None or vung_so.size == 0:
        return None
    _ghi_debug(thu_muc_debug, "buoc_04_vung_so.jpg", vung_so)

    H_v, W_v = vung_so.shape[:2]
    if H_v < 5 or W_v < 5:
        return None

    vung_so = deskew_vung_so(vung_so)
    _ghi_debug(thu_muc_debug, "buoc_04b_deskew.jpg", vung_so)

    vung_so, _ = hieu_chinh_shear_vung_bgr(vung_so, bo_doc)
    H_v, W_v = vung_so.shape[:2]
    _ghi_debug(thu_muc_debug, "buoc_04c_shear.jpg", vung_so)

    roi_te = tien_xu_ly_vung_te_nua(vung_so, bo_doc)
    if roi_te is None:
        roi_te = np.full((max(1, H_v), max(1, W_v)), 255, dtype=np.uint8)
    _ghi_debug(thu_muc_debug, "buoc_05b_te_inv_deskew.jpg", roi_te)

    Ht, Wt = roi_te.shape[:2]
    ys_row, _ = np.where(roi_te < 128)
    if len(ys_row) > 0:
        y_row0 = int(ys_row.min())
        y_row1 = int(ys_row.max()) + 1
    else:
        y_row0, y_row1 = 0, Ht
    pad_y_crop = max(8, int((y_row1 - y_row0) * 0.12))
    crop_y0_fix = max(0, y_row0 - pad_y_crop)
    crop_y1_fix = min(Ht, y_row1 + pad_y_crop)

    hop_ky_tu, hop_te_list = chia_o_snap_proj_roi_te(
        roi_te, crop_y0_fix, crop_y1_fix, W_v, SO_KY_TU, PAD_O
    )

    if thu_muc_debug:
        dbg = vung_so.copy()
        for k, (s_x, e_x) in enumerate(hop_ky_tu):
            cv2.rectangle(dbg, (s_x, 0), (e_x - 1, H_v - 1), (0, 220, 80), 1)
            cv2.putText(dbg, str(k + 1), (s_x + 3, 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 80), 1)
        _ghi_debug(thu_muc_debug, "buoc_05_chia_o.jpg", dbg)

    van_ban = ""
    nhan_conf = []
    ds_blank = []

    for k, (s_x, e_x) in enumerate(hop_ky_tu):
        o_bgr_k = vung_so[:, s_x:e_x]
        _, co_noi_dung = tien_xu_ly_o(o_bgr_k)

        s_te, e_te = hop_te_list[k]
        ma_roi = roi_te[crop_y0_fix:crop_y1_fix, s_te:e_te]
        ty_le_ma = float(np.mean(ma_roi < 128)) if ma_roi.size > 0 else 0.0
        if co_noi_dung and ty_le_ma < 0.02:
            co_noi_dung = False

        if not co_noi_dung:
            ds_blank.append(True)
            nhan_conf.append(('', 0.0))
            continue

        ds_blank.append(False)
        crop_x0 = max(0, s_te - 10)
        crop_x1 = min(Wt, e_te + DOT_CAPTURE_PAD)
        crop_inv = roi_te[crop_y0_fix:crop_y1_fix, crop_x0:crop_x1]
        crop_do = cv2.bitwise_not(crop_inv) if crop_inv.size else np.zeros((8, 8), dtype=np.uint8)

        ky, conf, _ = bo_doc.du_doan_ky_tu(crop_do)
        van_ban += ky
        nhan_conf.append((ky, conf))

    chuoi_raw = van_ban.strip()
    trong_luong = dinh_dang_trong_luong(chuoi_raw)
    trong_luong_float = ep_trong_luong_float(trong_luong)
    confs = [conf for idx, (_, conf) in enumerate(nhan_conf) if not ds_blank[idx]]
    do_tin_cay = float(np.mean(confs)) if confs else 0.0

    return {
        'trong_luong': trong_luong,
        'trong_luong_raw': chuoi_raw,
        'trong_luong_float': trong_luong_float,
        'do_tin_cay': do_tin_cay,
        'thoi_gian_ms': round((time.perf_counter() - t0) * 1000, 2),
        'nguon_nhan_dien': 'onnx',
    }


def nhan_dien_trong_luong_tu_bgr(anh_goc, thu_muc_debug=None, bo_doc=None, uu_tien_yolo=False):
    """
    Uu tien OpenCV LED 7 doan khong can train, fallback ONNX seven-seg cuc bo.
    YOLO chi chay khi truyen uu_tien_yolo=True va co weights chu so chuyen biet.
    Neu tat ca that bai thi tra 0.00 de van luu/van hien thi du lieu.
    """
    t0 = time.perf_counter()
    if uu_tien_yolo:
        ket_qua_yolo = nhan_dien_trong_luong_yolo_tu_bgr(anh_goc, thu_muc_debug=thu_muc_debug)
        if ket_qua_yolo and ket_qua_yolo.get('trong_luong_float') is not None:
            return ket_qua_yolo

    ket_qua_led = nhan_dien_led_7_doan_tu_bgr(
        anh_goc,
        thu_muc_debug=thu_muc_debug,
        bo_doc=bo_doc,
    )
    if ket_qua_led and ket_qua_led.get('trong_luong_float') is not None:
        return ket_qua_led

    try:
        ket_qua_onnx = nhan_dien_trong_luong_onnx_tu_bgr(
            anh_goc,
            thu_muc_debug=thu_muc_debug,
            bo_doc=bo_doc,
        )
        if ket_qua_onnx and ket_qua_onnx.get('trong_luong_float') is not None:
            return ket_qua_onnx
    except Exception as exc:
        print(f"  [WARN] ONNX nhan dien loi: {exc}")

    ket_qua = ket_qua_khong_nhan_dien('fallback_0')
    ket_qua['thoi_gian_ms'] = round((time.perf_counter() - t0) * 1000, 2)
    return ket_qua


def nhan_dien_trong_luong_tu_bytes(anh_bytes, thu_muc_debug=None, bo_doc=None):
    arr = np.frombuffer(anh_bytes, dtype=np.uint8)
    anh = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if anh is None:
        return ket_qua_khong_nhan_dien('decode_fail')
    return nhan_dien_trong_luong_tu_bgr(anh, thu_muc_debug=thu_muc_debug, bo_doc=bo_doc)


# ============================================================
# PHAN TICH CHINH
# ============================================================

def chay_phan_tich(duong_dan_anh, thu_muc_debug):
    os.makedirs(thu_muc_debug, exist_ok=True)
    anh_goc = cv2.imread(duong_dan_anh)
    if anh_goc is None:
        print(f"  [LOI] Khong doc duoc: '{duong_dan_anh}'")
        sys.exit(1)

    H_goc, W_goc = anh_goc.shape[:2]
    print(f"\n  Anh: {duong_dan_anh}  ({W_goc}x{H_goc}px)")
    print(f"  Debug: {thu_muc_debug}/\n")
    cv2.imwrite(f"{thu_muc_debug}/buoc_01_goc.jpg", anh_goc)

    anh_bgr, (roi_x0, roi_y0, roi_x1, roi_y1) = cat_roi_co_dinh_goc_phai_duoi(anh_goc)
    H, W = anh_bgr.shape[:2]
    if DUNG_ROI_CO_DINH_GOC_PHAI_DUOI:
        print(f"  ROI co dinh goc phai duoi: x=[{roi_x0},{roi_x1}) "
              f"y=[{roi_y0},{roi_y1})  ({W}x{H}px)")
        cv2.imwrite(f"{thu_muc_debug}/buoc_02_roi_goc_phai_duoi.jpg", anh_bgr)

    bo_doc = BoDocTrongLuong()
    t0     = time.perf_counter()

    # --- Tim hang ---
    _, toa_do, roi_bgr = bo_doc.tim_hang_dau_tien(anh_bgr)
    if roi_bgr is None:
        print("  [LOI] Khong tim thay hang!")
        return {'trong_luong': None, 'trong_luong_raw': None}
    cv2.imwrite(f"{thu_muc_debug}/buoc_03_hang1_crop.jpg", roi_bgr)
    H_c, W_c = roi_bgr.shape[:2]
    print(f"  Hang crop: {W_c}x{H_c}px")

    # --- Cat vien ---
    vung_so, (r0, r1, c0, c1) = cat_vien_sang(roi_bgr,
                                               nguong=NGUONG_VIEN_SANG,
                                               padding=PADDING_VIEN)
    cv2.imwrite(f"{thu_muc_debug}/buoc_04_vung_so.jpg", vung_so)
    H_v, W_v = vung_so.shape[:2]
    print(f"  Vung so sau cat vien: {W_v}x{H_v}px")
    if H_v < 5 or W_v < 5:
        print("  [LOI] Vung qua nho!")
        return {'trong_luong': None, 'trong_luong_raw': None}

    # --- Deskew (xoay nhe) ---
    vung_so = deskew_vung_so(vung_so)
    cv2.imwrite(f"{thu_muc_debug}/buoc_04b_deskew.jpg", vung_so)
    H_v, W_v = vung_so.shape[:2]
    print(f"  Vung so sau deskew: {W_v}x{H_v}px")

    # --- Shear (can hang so nghieng truoc khi chia o thang) ---
    vung_so, sf_shear = hieu_chinh_shear_vung_bgr(vung_so, bo_doc)
    H_v, W_v = vung_so.shape[:2]
    if abs(sf_shear) >= 0.008:
        print(f"  [Shear] hieu chinh nghieng: sf={sf_shear:+.4f}")
    cv2.imwrite(f"{thu_muc_debug}/buoc_04c_shear.jpg", vung_so)
    print(f"  Vung so sau shear: {W_v}x{H_v}px")

    # --- Teo toan hang + chia o snap theo thung lung (trung buoc_05b, tranh cat lech) ---
    roi_te = tien_xu_ly_vung_te_nua(vung_so, bo_doc)
    if roi_te is None:
        roi_te = np.full((max(1, H_v), max(1, W_v)), 255, dtype=np.uint8)
    cv2.imwrite(f"{thu_muc_debug}/buoc_05b_te_inv_deskew.jpg", roi_te)

    Ht, Wt = roi_te.shape[:2]
    ys_row, _ = np.where(roi_te < 128)
    if len(ys_row) > 0:
        y_row0 = int(ys_row.min())
        y_row1 = int(ys_row.max()) + 1
    else:
        y_row0, y_row1 = 0, Ht
    pad_y_crop  = max(8, int((y_row1 - y_row0) * 0.12))
    crop_y0_fix = max(0, y_row0 - pad_y_crop)
    crop_y1_fix = min(Ht, y_row1 + pad_y_crop)

    hop_ky_tu, hop_te_list = chia_o_snap_proj_roi_te(
        roi_te, crop_y0_fix, crop_y1_fix, W_v, SO_KY_TU, PAD_O
    )

    # Debug chia o (khung trung ranh snap + buoc_05b)
    dbg = vung_so.copy()
    for k, (s_x, e_x) in enumerate(hop_ky_tu):
        cv2.rectangle(dbg, (s_x, 0), (e_x-1, H_v-1), (0, 220, 80), 1)
        cv2.putText(dbg, str(k+1), (s_x+3, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 80), 1)
    cv2.imwrite(f"{thu_muc_debug}/buoc_05_chia_o.jpg", dbg)

    # --- Nhan dien ---
    van_ban       = ""
    nhan_conf     = []
    cac_anh_ky_tu = []
    ds_blank      = []

    for k, (s_x, e_x) in enumerate(hop_ky_tu):
        o_bgr_k = vung_so[:, s_x:e_x]

        gray_led, co_noi_dung = tien_xu_ly_o(o_bgr_k)

        s_te, e_te = hop_te_list[k]
        ma_roi = roi_te[crop_y0_fix:crop_y1_fix, s_te:e_te]
        ty_le_ma = float(np.mean(ma_roi < 128)) if ma_roi.size > 0 else 0.0
        # Bo qua o gan het sang (khong net tren buoc_05b) — giam nham 1 cot thanh so
        if co_noi_dung and ty_le_ma < 0.02:
            co_noi_dung = False

        # Debug: luu gray va binary (kenh do cu — chi de debug)
        _, o_bin_dbg = cv2.threshold(gray_led, 30, 255, cv2.THRESH_BINARY)
        cv2.imwrite(f"{thu_muc_debug}/o_{k+1:02d}_gray.jpg", gray_led)
        cv2.imwrite(f"{thu_muc_debug}/o_{k+1:02d}_bin.jpg",  o_bin_dbg)

        if not co_noi_dung:
            ds_blank.append(True)
            nhan_conf.append(('', 0.0))
            cac_anh_ky_tu.append(np.zeros((32, 32), dtype=np.uint8))
            cv2.imwrite(f"{thu_muc_debug}/o_{k+1:02d}_blank.jpg", o_bgr_k)
            continue

        ds_blank.append(False)
        crop_x0 = max(0, s_te - 10)
        crop_x1 = min(Wt, e_te + DOT_CAPTURE_PAD)
        crop_inv = roi_te[crop_y0_fix:crop_y1_fix, crop_x0:crop_x1]
        if crop_inv.size == 0:
            crop_do = np.zeros((8, 8), dtype=np.uint8)
        else:
            crop_do = cv2.bitwise_not(crop_inv)

        ky, conf, anh_32 = bo_doc.du_doan_ky_tu(crop_do)
        van_ban += ky
        nhan_conf.append((ky, conf))
        cac_anh_ky_tu.append(anh_32)
        cv2.imwrite(f"{thu_muc_debug}/o_{k+1:02d}_{ky}.jpg", o_bgr_k)

    # Panel: ty le cot = rong tren vung_so (trung buoc_05 chia o)
    cac_rong_vung = [max(1, e_x - s_x) for s_x, e_x in hop_ky_tu]
    panel = tao_panel_ky_tu(
        cac_anh_ky_tu, nhan_conf, ds_blank,
        cac_rong_o_px=cac_rong_vung, cao_tham_chieu_px=H_v)
    cv2.imwrite(f"{thu_muc_debug}/buoc_06_panel_ky_tu.jpg", panel)

    thoi_gian_ms = round((time.perf_counter() - t0) * 1000, 2)
    chuoi_raw    = van_ban.strip()
    trong_luong  = dinh_dang_trong_luong(chuoi_raw)

    print(f"\n  {'='*50}")
    print(f"  TRONG LUONG: {trong_luong} kg  (raw: '{chuoi_raw}')")
    print(f"  Thoi gian  : {thoi_gian_ms} ms")
    so_co_nd = sum(1 for b in ds_blank if not b)
    print(f"  Chia {SO_KY_TU} o | co nd: {so_co_nd}/{SO_KY_TU}")
    print(f"\n  {'STT':<4} {'So':<6} {'Tin cay':>8}")
    print(f"  {'-'*30}")
    for j, (ky, conf) in enumerate(nhan_conf):
        if ds_blank[j]:
            print(f"  [{j+1:>2}]  {'[ ]':<6}  {'---':>6}   (o trong)")
        else:
            bar = '#'*int(conf*20) + '.'*(20-int(conf*20))
            print(f"  [{j+1:>2}]  '{ky}'    {conf:>6.1%}   {bar}")
    print(f"  {'='*50}\n")

    return {
        'trong_luong':     trong_luong,
        'trong_luong_raw': chuoi_raw,
        'thoi_gian_ms':    thoi_gian_ms,
    }


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 50)
    print("  NHAN DIEN TRONG LUONG (HANG 1)")
    print("=" * 50)
    print()
    try:
        duong_dan_anh = input(
            "  Nhap duong dan anh (Enter = '1.jpg'): "
        ).strip().strip('"').strip("'")
    except KeyboardInterrupt:
        sys.exit(0)
    if not duong_dan_anh:
        duong_dan_anh = "1.jpg"
    if not os.path.exists(duong_dan_anh):
        print(f"  [LOI] Khong tim thay: '{duong_dan_anh}'")
        sys.exit(1)
    ten_goc       = os.path.splitext(os.path.basename(duong_dan_anh))[0]
    thu_muc_debug = f"debug_tl_{ten_goc}"
    ket_qua = chay_phan_tich(duong_dan_anh, thu_muc_debug)
    print(f"  Ket qua: {ket_qua}")


if __name__ == "__main__":
    main()
