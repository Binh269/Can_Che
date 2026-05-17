/**
 * chi_tiet_can.js
 * - Polling du lieu can theo thoi gian thuc
 * - Tai lich su ban ghi co phan trang
 * - Xu ly camera WebRTC (goi webrtc.js)
 * - Xem anh phong to
 * KHONG chua HTML hay CSS
 */

var KHOANG_CACH_POLLING = 5000;
var trang_lich_su_hien_tai = 1;
var camera_hien_tai = null;
var api_can_hien_tai = '';
var api_nhan_dien_hien_tai = '';
var img_stream_truc_tiep = null;
var dang_tai_du_lieu_can = false;
var dang_tai_lich_su = false;
var dang_tai_nhan_dien = false;
var nhan_dien_truc_tuyen_dang_chay = false;
var interval_nhan_dien_truc_tuyen = null;
var KHOANG_CACH_NHAN_DIEN_TRUC_TUYEN = 1500;

// ─────────────────────────────────────────────────────────────
// Khoi dong
// ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    var dl = document.getElementById('du-lieu-trang');
    if (!dl) return;

    var ma_can = dl.getAttribute('data-ma-can');
    api_can_hien_tai = dl.getAttribute('data-api-can') || '';
    api_nhan_dien_hien_tai = dl.getAttribute('data-api-nhan-dien') || '';
    var api_du_lieu = dl.getAttribute('data-api-du-lieu');
    var api_lich_su = dl.getAttribute('data-api-lich-su');
    var api_sua = dl.getAttribute('data-api-sua');
    var cho_phep_sua = dl.getAttribute('data-cho-phep-sua') === '1';
    var cameras = JSON.parse(dl.getAttribute('data-cameras') || '[]');

    // Uu tien stream cua can, chi fallback sang camera kem theo neu can khong co api
    if (api_can_hien_tai) {
        camera_hien_tai = {
            id: 0,
            ten: 'API của cân',
            api: api_can_hien_tai
        };
    } else if (cameras.length > 0 && cameras[0].api) {
        camera_hien_tai = cameras[0];
    }

    // Bat su kien selector camera (neu co nhieu camera)
    var selector = document.getElementById('chon-camera');
    if (selector) {
        selector.addEventListener('change', function () {
            var camera_id = parseInt(this.value);
            var camera_duoc_chon = cameras.find(function (c) { return c.id === camera_id; }) || null;
            if (!api_can_hien_tai && camera_duoc_chon && camera_duoc_chon.api) {
                camera_hien_tai = camera_duoc_chon;
            } else if (api_can_hien_tai) {
                camera_hien_tai = {
                    id: 0,
                    ten: 'API của cân',
                    api: api_can_hien_tai
                };
            } else {
                camera_hien_tai = null;
            }
        });
    }

    // Polling du lieu can
    capNhatDuLieuCan(api_du_lieu);
    setInterval(function () { capNhatDuLieuCan(api_du_lieu); }, KHOANG_CACH_POLLING);

    // Tai lich su lan dau
    taiLichSu(api_lich_su, 1);
    setInterval(function () {
        capNhatLichSuNgam(api_lich_su);
    }, KHOANG_CACH_POLLING);

    // Nut lam moi lich su
    var btn_lam_moi = document.getElementById('btn-lam-moi-lich-su');
    if (btn_lam_moi) btn_lam_moi.addEventListener('click', function () {
        taiLichSu(api_lich_su, trang_lich_su_hien_tai);
    });

    // Nut sua thong tin can
    var btn_mo_sua = document.getElementById('btn-mo-sua-can');
    if (btn_mo_sua && api_sua) btn_mo_sua.addEventListener('click', function () {
        moModalSuaCan();
    });

    var btn_dong_sua = document.getElementById('btn-dong-sua-can');
    if (btn_dong_sua) btn_dong_sua.addEventListener('click', function () {
        dongModalSuaCan();
    });

    var btn_luu_sua = document.getElementById('btn-luu-sua-can');
    if (btn_luu_sua && api_sua) btn_luu_sua.addEventListener('click', function () {
        luuSuaCan(api_sua);
    });

    var modal_sua = document.getElementById('modal-sua-can');
    if (modal_sua) modal_sua.addEventListener('click', function (e) {
        if (e.target === modal_sua) dongModalSuaCan();
    });

    // Nut bat dau stream
    var btn_bat_dau = document.getElementById('btn-bat-dau-stream');
    if (btn_bat_dau) btn_bat_dau.addEventListener('click', function () {
        batDauStream();
    });

    // Nut dung stream
    var btn_dung = document.getElementById('btn-dung-stream');
    if (btn_dung) btn_dung.addEventListener('click', function () {
        dungStream();
    });

    // Dong modal anh khi click ben ngoai
    var modal_anh = document.getElementById('modal-anh');
    if (modal_anh) modal_anh.addEventListener('click', function (e) {
        if (e.target === modal_anh) dongModalAnh();
    });
});

// ─────────────────────────────────────────────────────────────
// Cap nhat du lieu can real-time
// ─────────────────────────────────────────────────────────────
function capNhatDuLieuCan(api_url) {
    if (!api_url || dang_tai_du_lieu_can) return;
    dang_tai_du_lieu_can = true;

    var dl = document.getElementById('du-lieu-trang');
    var kl_toi_da = dl ? parseFloat(dl.getAttribute('data-kl-toi-da')) : NaN;

    fetch(api_url, { cache: 'no-store' })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            if (!data.co_du_lieu) return;

            if (nhan_dien_truc_tuyen_dang_chay) {
                if (data.anh) {
                    capNhatAnhMoiNhat(data.anh);
                }
                return;
            }

            // Cap nhat so khoi luong
            var phan_tu_kl = document.getElementById('kl-hien-tai');
            if (phan_tu_kl) phan_tu_kl.textContent = parseFloat(data.khoi_luong).toFixed(1);

            // Cap nhat thanh tai trong
            var phan_tram = Math.min(100, (data.khoi_luong / kl_toi_da) * 100);
            var thanh = document.getElementById('thanh-tai-trong');
            if (thanh) {
                thanh.style.width = phan_tram + '%';
                if (phan_tram >= 90) {
                    thanh.classList.add('nguy-hiem');
                } else {
                    thanh.classList.remove('nguy-hiem');
                }
            }

            // Cap nhat text phan tram
            var phan_tu_pt = document.getElementById('phan-tram-tai');
            if (phan_tu_pt) {
                phan_tu_pt.textContent = 'Tải trọng: ' + phan_tram.toFixed(1) + '% / ' + kl_toi_da + ' kg';
            }

            // Cap nhat thoi gian
            var phan_tu_tg = document.getElementById('thoi-gian-do');
            if (phan_tu_tg) phan_tu_tg.textContent = 'Đo lúc: ' + data.thoi_gian;

            // Cap nhat anh moi nhat
            if (data.anh) {
                capNhatAnhMoiNhat(data.anh);
            }
        })
        .catch(function () {})
        .finally(function () {
            dang_tai_du_lieu_can = false;
        });
}

function capNhatKhoiLuongHienTai(khoi_luong, thoi_gian, ghi_chu) {
    var dl = document.getElementById('du-lieu-trang');
    var kl_toi_da = dl ? parseFloat(dl.getAttribute('data-kl-toi-da')) : NaN;
    var gia_tri = parseFloat(khoi_luong);
    if (isNaN(gia_tri)) return;

    var phan_tu_kl = document.getElementById('kl-hien-tai');
    if (phan_tu_kl) phan_tu_kl.textContent = gia_tri.toFixed(2);

    var phan_tram = kl_toi_da > 0 ? Math.min(100, (gia_tri / kl_toi_da) * 100) : 0;
    var thanh = document.getElementById('thanh-tai-trong');
    if (thanh) {
        thanh.style.width = phan_tram + '%';
        if (phan_tram >= 90) thanh.classList.add('nguy-hiem');
        else thanh.classList.remove('nguy-hiem');
    }

    var phan_tu_pt = document.getElementById('phan-tram-tai');
    if (phan_tu_pt) {
        phan_tu_pt.textContent = 'Tai trong: ' + phan_tram.toFixed(1) + '% / ' + kl_toi_da + ' kg';
    }

    var phan_tu_tg = document.getElementById('thoi-gian-do');
    if (phan_tu_tg) {
        phan_tu_tg.textContent = (ghi_chu || 'Nhan dien') + ': ' + (thoi_gian || '');
    }
}

function batDauNhanDienTrucTuyen() {
    if (!api_nhan_dien_hien_tai || interval_nhan_dien_truc_tuyen) return;
    nhan_dien_truc_tuyen_dang_chay = true;
    capNhatNhanDienTrucTuyen();
    interval_nhan_dien_truc_tuyen = setInterval(
        capNhatNhanDienTrucTuyen,
        KHOANG_CACH_NHAN_DIEN_TRUC_TUYEN
    );
}

function dungNhanDienTrucTuyen() {
    nhan_dien_truc_tuyen_dang_chay = false;
    dang_tai_nhan_dien = false;
    if (interval_nhan_dien_truc_tuyen) {
        clearInterval(interval_nhan_dien_truc_tuyen);
        interval_nhan_dien_truc_tuyen = null;
    }
}

function capNhatNhanDienTrucTuyen() {
    if (!api_nhan_dien_hien_tai || dang_tai_nhan_dien) return;
    dang_tai_nhan_dien = true;

    fetch(api_nhan_dien_hien_tai, { cache: 'no-store' })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            if (data.co_du_lieu) {
                capNhatKhoiLuongHienTai(data.khoi_luong, data.thoi_gian, 'Nhan dien truc tuyen');
            }
        })
        .catch(function () {})
        .finally(function () {
            dang_tai_nhan_dien = false;
        });
}

function capNhatAnhMoiNhat(url_anh) {
    var khu_anh = document.getElementById('khu-anh-moi-nhat');
    if (!khu_anh) return;

    // Neu chua co anh thi tao moi, neu co roi thi cap nhat src
    var anh_hien_co = khu_anh.querySelector('img');
    if (anh_hien_co) {
        anh_hien_co.src = url_anh;
    } else {
        khu_anh.innerHTML = '';
        var anh = document.createElement('img');
        anh.src = url_anh;
        anh.alt = 'Anh can moi nhat';
        anh.style.maxWidth = '100%';
        anh.style.maxHeight = '200px';
        anh.style.borderRadius = '8px';
        anh.style.cursor = 'pointer';
        anh.addEventListener('click', function () { moModalAnh(url_anh); });
        khu_anh.appendChild(anh);
    }
}

function moModalSuaCan() {
    var modal = document.getElementById('modal-sua-can');
    if (!modal) return;
    modal.classList.add('hien');
}

function dongModalSuaCan() {
    var modal = document.getElementById('modal-sua-can');
    if (modal) modal.classList.remove('hien');
}

function luuSuaCan(api_url) {
    var btn_luu = document.getElementById('btn-luu-sua-can');
    if (btn_luu) btn_luu.disabled = true;

    var payload = {
        ten_can: document.getElementById('sua-ten-can') ? document.getElementById('sua-ten-can').value.trim() : '',
        vi_tri: document.getElementById('sua-vi-tri') ? document.getElementById('sua-vi-tri').value.trim() : '',
        hang: document.getElementById('sua-hang') ? document.getElementById('sua-hang').value.trim() : '',
        ngay_lap_dat: document.getElementById('sua-ngay-lap-dat') ? document.getElementById('sua-ngay-lap-dat').value : '',
        khoi_luong_toi_da: document.getElementById('sua-khoi-luong-toi-da') ? document.getElementById('sua-khoi-luong-toi-da').value : '',
        api: document.getElementById('sua-api') ? document.getElementById('sua-api').value.trim() : '',
        hoat_dong: document.getElementById('sua-hoat-dong') ? document.getElementById('sua-hoat-dong').checked : false
    };

    fetch(api_url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': (window.layCSRFToken ? window.layCSRFToken() : '')
        },
        body: JSON.stringify(payload)
    })
        .then(function (res) { return res.json().then(function (data) { return { status: res.status, data: data }; }); })
        .then(function (ket_qua) {
            var data = ket_qua.data;
            if (!data.thanh_cong) {
                window.hienThiThongBao(data.loi || 'Không thể cập nhật thông tin cân', 'loi');
                return;
            }

            capNhatHienThiThongTinCan(data.can);
            capNhatDuLieuCan(document.getElementById('du-lieu-trang').getAttribute('data-api-du-lieu'));
            window.hienThiThongBao('Đã cập nhật thông tin cân', 'thanh-cong');
            dongModalSuaCan();
        })
        .catch(function () {
            window.hienThiThongBao('Không thể cập nhật thông tin cân', 'loi');
        })
        .finally(function () {
            if (btn_luu) btn_luu.disabled = false;
        });
}

function capNhatHienThiThongTinCan(can) {
    if (!can) return;

    var tieu_de = document.querySelector('.tieu-de-chi-tiet h1');
    if (tieu_de) tieu_de.textContent = can.ten_can;

    var ma_can = document.getElementById('gt-ma-can');
    var hang = document.getElementById('gt-hang');
    var vi_tri = document.getElementById('gt-vi-tri');
    var ngay_lap_dat = document.getElementById('gt-ngay-lap-dat');
    var khoi_luong_toi_da = document.getElementById('gt-khoi-luong-toi-da');
    var trang_thai = document.getElementById('gt-trang-thai-can');

    if (ma_can) ma_can.textContent = can.ma_can;
    if (hang) hang.textContent = can.hang;
    if (vi_tri) vi_tri.textContent = can.vi_tri;
    if (ngay_lap_dat) ngay_lap_dat.textContent = can.ngay_lap_dat;
    if (khoi_luong_toi_da) khoi_luong_toi_da.textContent = parseFloat(can.khoi_luong_toi_da).toFixed(1) + ' kg';
    if (trang_thai) trang_thai.textContent = can.hoat_dong ? '🟢 Hoạt động' : '🔴 Tắt';

    var badge_trang_thai = document.querySelector('.tieu-de-chi-tiet .badge');
    if (badge_trang_thai) {
        if (can.hoat_dong) {
            badge_trang_thai.className = 'badge badge-xanh-la';
            badge_trang_thai.innerHTML = '<span class="dot-nhap-nhay"></span> Đang hoạt động';
        } else {
            badge_trang_thai.className = 'badge badge-do';
            badge_trang_thai.textContent = '⏹ Đã tắt';
        }
    }

    var dl = document.getElementById('du-lieu-trang');
    if (dl) dl.setAttribute('data-kl-toi-da', can.khoi_luong_toi_da);
}

// ─────────────────────────────────────────────────────────────
// Lich su ban ghi
// ─────────────────────────────────────────────────────────────
function taiLichSu(api_url, trang, chay_ngam) {
    if (!api_url || dang_tai_lich_su) return;
    dang_tai_lich_su = true;

    trang_lich_su_hien_tai = trang;
    var body_bang = document.getElementById('body-lich-su');
    if (!body_bang) {
        dang_tai_lich_su = false;
        return;
    }

    body_bang.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--mau-chu-mo);padding:24px">Đang tải...</td></tr>';

    fetch(api_url + '?trang=' + trang, { cache: 'no-store' })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            hienThiBangLichSu(data, api_url);
            dang_tai_lich_su = false;
        })
        .catch(function () {
            body_bang.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--mau-do)">Không tải được dữ liệu</td></tr>';
        })
        .finally(function () {
            dang_tai_lich_su = false;
        });
}

function capNhatLichSuNgam(api_url) {
    if (!api_url || dang_tai_lich_su) return;
    dang_tai_lich_su = true;

    fetch(api_url + '?trang=' + trang_lich_su_hien_tai, { cache: 'no-store' })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            hienThiBangLichSu(data, api_url);
        })
        .catch(function () {})
        .finally(function () {
            dang_tai_lich_su = false;
        });
}

function hienThiBangLichSu(data, api_url) {
    var body_bang = document.getElementById('body-lich-su');
    var khu_phan_trang = document.getElementById('phan-trang');
    if (!body_bang) return;

    if (!data.ban_ghi || data.ban_ghi.length === 0) {
        body_bang.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--mau-chu-mo);padding:32px">Chưa có bản ghi nào</td></tr>';
        if (khu_phan_trang) khu_phan_trang.innerHTML = '';
        return;
    }

    var html = '';
    data.ban_ghi.forEach(function (ban_ghi, chi_so) {
        var stt = (data.trang - 1) * 20 + chi_so + 1;
        html += '<tr class="hang-ban-ghi">';
        html += '<td style="color:var(--mau-chu-mo)">' + stt + '</td>';
        html += '<td class="khoi-luong-cell">' + parseFloat(ban_ghi.khoi_luong).toFixed(2) + ' kg</td>';
        html += '<td>' + ban_ghi.thoi_gian + '</td>';
        html += '<td>';
        if (ban_ghi.anh) {
            html += '<img src="' + ban_ghi.anh + '" alt="anh" class="anh-nho" data-url="' + ban_ghi.anh + '">';
        } else {
            html += '<span style="color:var(--mau-chu-min)">—</span>';
        }
        html += '</td>';
        html += '</tr>';
    });
    body_bang.innerHTML = html;

    // Gan su kien click anh
    body_bang.querySelectorAll('.anh-nho').forEach(function (anh) {
        anh.addEventListener('click', function () {
            moModalAnh(this.getAttribute('data-url'));
        });
    });

    // Phan trang
    hienThiPhanTrang(data, api_url, khu_phan_trang);
}

function hienThiPhanTrang(data, api_url, khu_phan_trang) {
    if (!khu_phan_trang) return;
    if (data.so_trang <= 1) { khu_phan_trang.innerHTML = ''; return; }

    var html = '';
    // Nut trang truoc
    html += '<button class="btn-phan-trang" ' + (data.trang <= 1 ? 'disabled' : '') + ' data-trang="' + (data.trang - 1) + '">← Trước</button>';
    // Cac trang
    var bat_dau = Math.max(1, data.trang - 2);
    var ket_thuc = Math.min(data.so_trang, data.trang + 2);
    for (var i = bat_dau; i <= ket_thuc; i++) {
        html += '<button class="btn-phan-trang' + (i === data.trang ? ' active' : '') + '" data-trang="' + i + '">' + i + '</button>';
    }
    // Nut trang sau
    html += '<button class="btn-phan-trang" ' + (data.trang >= data.so_trang ? 'disabled' : '') + ' data-trang="' + (data.trang + 1) + '">Sau →</button>';

    khu_phan_trang.innerHTML = html;

    // Gan su kien
    khu_phan_trang.querySelectorAll('.btn-phan-trang:not([disabled])').forEach(function (btn) {
        btn.addEventListener('click', function () {
            taiLichSu(api_url, parseInt(this.getAttribute('data-trang')));
        });
    });
}

// ─────────────────────────────────────────────────────────────
// Camera stream
// ─────────────────────────────────────────────────────────────
function batDauStream() {
    if (!camera_hien_tai) {
        window.hienThiThongBao('Không có URL stream nào được cấu hình', 'canh-bao');
        return;
    }

    var video = document.getElementById('video-stream');
    var btn_bat = document.getElementById('btn-bat-dau-stream');
    var btn_dung = document.getElementById('btn-dung-stream');
    var man_hinh_cho = document.getElementById('man-hinh-cho');
    var trang_thai_stream = document.getElementById('trang-thai-stream');
    var trang_thai_kt = document.getElementById('trang-thai-ket-noi');
    var api_stream = camera_hien_tai.api || api_can_hien_tai;

    if (!api_stream) {
        window.hienThiThongBao('Thiếu địa chỉ stream cho cân này', 'loi');
        return;
    }

    // Stream dang http/https thi mo truc tiep bang iframe, khong thu WebRTC proxy nua
    if (api_stream.startsWith('http://') || api_stream.startsWith('https://')) {
        moStreamTrucTiep(api_stream);
        batDauNhanDienTrucTuyen();
        if (window.hienThiThongBao) {
            window.hienThiThongBao('Đang mở trực tiếp bằng iframe', 'thong-tin');
        }
        return;
    }

    if (trang_thai_kt) {
        trang_thai_kt.textContent = 'Đang mở: ' + api_stream;
    }

    // Goi webrtc.js
    window.batDauWebRTC(
        api_stream,
        video,
        function (trang_thai) {
            if (trang_thai === 'dang_ket_noi') {
                if (trang_thai_kt) trang_thai_kt.textContent = 'Đang kết nối...';
            } else if (trang_thai === 'da_ket_noi') {
                if (man_hinh_cho) man_hinh_cho.style.display = 'none';
                if (trang_thai_stream) trang_thai_stream.style.display = 'flex';
                if (btn_bat) btn_bat.style.display = 'none';
                if (btn_dung) btn_dung.style.display = '';
                batDauNhanDienTrucTuyen();
                if (trang_thai_kt) trang_thai_kt.textContent = 'Đang stream';
                window.hienThiThongBao('Camera đã kết nối', 'thanh-cong');
            } else if (trang_thai === 'mat_ket_noi') {
                dungNhanDienTrucTuyen();
                if (man_hinh_cho) man_hinh_cho.style.display = 'flex';
                if (trang_thai_stream) trang_thai_stream.style.display = 'none';
                if (btn_bat) btn_bat.style.display = '';
                if (btn_dung) btn_dung.style.display = 'none';
                if (trang_thai_kt) trang_thai_kt.textContent = 'Mất kết nối';
                window.hienThiThongBao('Camera mất kết nối', 'canh-bao');
            } else if (trang_thai === 'loi') {
                dungNhanDienTrucTuyen();
                if (trang_thai_kt) trang_thai_kt.textContent = 'Lỗi kết nối';
                window.hienThiThongBao('Không thể kết nối stream: ' + api_stream, 'loi');
            }
        }
    );
}

function xuLyThatBaiWebRTCHTTP(loi, api_stream) {
    if (!loi) return false;

    var thong_bao = loi.message || '';
    var la_405 = thong_bao.indexOf('405') !== -1;

    if (!la_405) return false;

    moStreamTrucTiep(api_stream);
    batDauNhanDienTrucTuyen();
    if (window.hienThiThongBao) {
        window.hienThiThongBao('Endpoint này không hỗ trợ WebRTC POST, đã chuyển sang mở trực tiếp', 'canh-bao');
    }
    return true;
}

function moStreamTrucTiep(api_stream) {
    var khu_camera = document.getElementById('khung-camera');
    var video = document.getElementById('video-stream');
    var man_hinh_cho = document.getElementById('man-hinh-cho');
    var trang_thai_stream = document.getElementById('trang-thai-stream');
    var btn_bat = document.getElementById('btn-bat-dau-stream');
    var btn_dung = document.getElementById('btn-dung-stream');
    var trang_thai_kt = document.getElementById('trang-thai-ket-noi');

    if (!khu_camera || !api_stream) return;

    var thong_tin_url = tachThongTinUrl(api_stream);
    var url_sach = thong_tin_url.url;

    if (video) video.style.display = 'none';
    if (man_hinh_cho) man_hinh_cho.style.display = 'none';
    if (trang_thai_stream) trang_thai_stream.style.display = 'flex';
    if (btn_bat) btn_bat.style.display = 'none';
    if (btn_dung) btn_dung.style.display = '';
    if (trang_thai_kt) trang_thai_kt.textContent = 'Đang mở trực tiếp';

    if (!img_stream_truc_tiep) {
        img_stream_truc_tiep = document.createElement('img');
        img_stream_truc_tiep.id = 'img-stream-truc-tiep';
        img_stream_truc_tiep.className = 'img-stream-truc-tiep';
        img_stream_truc_tiep.alt = 'Luồng stream trực tiếp';
    }

    img_stream_truc_tiep.src = url_sach;
    if (img_stream_truc_tiep.parentNode !== khu_camera) {
        khu_camera.appendChild(img_stream_truc_tiep);
    }
}

function tachThongTinUrl(raw_url) {
    try {
        var parsed = new URL(raw_url);
        var username = parsed.username ? decodeURIComponent(parsed.username) : '';
        var password = parsed.password ? decodeURIComponent(parsed.password) : '';
        parsed.username = '';
        parsed.password = '';
        return {
            url: parsed.toString(),
            username: username,
            password: password
        };
    } catch (loi) {
        return { url: raw_url, username: '', password: '' };
    }
}

function dungStream() {
    var video = document.getElementById('video-stream');
    var btn_bat = document.getElementById('btn-bat-dau-stream');
    var btn_dung = document.getElementById('btn-dung-stream');
    var man_hinh_cho = document.getElementById('man-hinh-cho');
    var trang_thai_stream = document.getElementById('trang-thai-stream');
    var trang_thai_kt = document.getElementById('trang-thai-ket-noi');

    dungNhanDienTrucTuyen();
    window.dungWebRTC();
    if (video) {
        video.srcObject = null;
        video.style.display = '';
    }
    if (img_stream_truc_tiep) {
        img_stream_truc_tiep.src = '';
        img_stream_truc_tiep.remove();
        img_stream_truc_tiep = null;
    }
    if (man_hinh_cho) man_hinh_cho.style.display = 'flex';
    if (trang_thai_stream) trang_thai_stream.style.display = 'none';
    if (btn_bat) btn_bat.style.display = '';
    if (btn_dung) btn_dung.style.display = 'none';
    if (trang_thai_kt) trang_thai_kt.textContent = 'Đã dừng';
    window.hienThiThongBao('Đã dừng stream camera', 'thong-tin');
}

window.xuLyThatBaiWebRTCHTTP = xuLyThatBaiWebRTCHTTP;

// ─────────────────────────────────────────────────────────────
// Modal xem anh lon
// ─────────────────────────────────────────────────────────────
function moModalAnh(url_anh) {
    var modal = document.getElementById('modal-anh');
    var anh = document.getElementById('anh-phong-to');
    if (!modal || !anh) return;
    anh.src = url_anh;
    modal.classList.add('hien');
}

function dongModalAnh() {
    var modal = document.getElementById('modal-anh');
    if (modal) modal.classList.remove('hien');
}
