/**
 * trang_chu.js
 * - He thong thong bao (msg class) - tu dong an sau 5 giay
 * - Polling cap nhat du lieu can tren trang chu moi 5 giay
 * - Ve bieu do Chart.js du lieu lich su tat ca can
 * - Hien thi bang lich su tong hop
 * KHONG chua HTML hay CSS
 */

// ─────────────────────────────────────────────────────────────
// He thong thong bao
// ─────────────────────────────────────────────────────────────

function hienThiThongBao(noi_dung, loai) {
    loai = loai || 'thong-tin';
    var vung = document.getElementById('vung-thong-bao');
    if (!vung) return;
    var bieu_tuong = { 'thanh-cong': '✅', 'loi': '❌', 'canh-bao': '⚠️', 'thong-tin': 'ℹ️' };
    var phan_tu = document.createElement('div');
    phan_tu.className = 'msg-item msg-' + loai;
    phan_tu.innerHTML = '<span>' + (bieu_tuong[loai] || 'ℹ️') + '</span><span>' + noi_dung + '</span>';
    vung.appendChild(phan_tu);
    setTimeout(function () {
        phan_tu.classList.add('an-di');
        setTimeout(function () {
            if (phan_tu.parentNode) phan_tu.parentNode.removeChild(phan_tu);
        }, 380);
    }, 5000);
}
window.hienThiThongBao = hienThiThongBao;

function layCSRFToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}
window.layCSRFToken = layCSRFToken;

function guiPost(url, du_lieu, callback_thanh_cong, callback_loi) {
    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': layCSRFToken() },
        body: JSON.stringify(du_lieu)
    })
    .then(function (res) { return res.json(); })
    .then(function (ket_qua) {
        if (ket_qua.thanh_cong) { if (callback_thanh_cong) callback_thanh_cong(ket_qua); }
        else { hienThiThongBao(ket_qua.loi || 'Có lỗi xảy ra', 'loi'); if (callback_loi) callback_loi(ket_qua); }
    })
    .catch(function (loi) { hienThiThongBao('Lỗi kết nối máy chủ', 'loi'); if (callback_loi) callback_loi(loi); });
}
window.guiPost = guiPost;

// ─────────────────────────────────────────────────────────────
// Mau sac cho tung can
// ─────────────────────────────────────────────────────────────
var MAU_CAN = [
    { duong: '#0070e0', nen: 'rgba(0,112,224,0.08)' },
    { duong: '#00a65a', nen: 'rgba(0,166,90,0.08)' },
    { duong: '#d97706', nen: 'rgba(217,119,6,0.08)' },
    { duong: '#7c3aed', nen: 'rgba(124,58,237,0.08)' },
];

// ─────────────────────────────────────────────────────────────
// Bien toan cuc
// ─────────────────────────────────────────────────────────────
var doi_tuong_bieu_do = null;
var da_co_bieu_do = false;
var KHOANG_CACH = 5000;

function chuyenThanhSo(gia_tri) {
    if (gia_tri === null || gia_tri === undefined || gia_tri === '') return null;
    var so = parseFloat(String(gia_tri).replace(',', '.'));
    return Number.isFinite(so) ? so : null;
}

function hienTrangThaiBieuDo(thong_bao) {
    var canvas = document.getElementById('bieu-do-khoi-luong');
    var khu_trong = document.getElementById('bieu-do-trong');
    if (canvas) canvas.style.display = 'none';
    if (khu_trong) {
        khu_trong.style.display = 'flex';
        var dong_chinh = khu_trong.querySelector('p');
        if (dong_chinh && thong_bao) dong_chinh.textContent = thong_bao;
    }
}

function hienCanvasBieuDo() {
    var canvas = document.getElementById('bieu-do-khoi-luong');
    var khu_trong = document.getElementById('bieu-do-trong');
    if (canvas) canvas.style.display = '';
    if (khu_trong) khu_trong.style.display = 'none';
    return canvas;
}

function chuanHoaDuLieuBieuDo(ket_qua_api) {
    if (!Array.isArray(ket_qua_api)) return [];

    return ket_qua_api.map(function (can) {
        var du_lieu = Array.isArray(can.du_lieu) ? can.du_lieu : [];
        return {
            ma_can: can.ma_can || '',
            ten_can: can.ten_can || can.ma_can || 'Can',
            du_lieu: du_lieu.map(function (d, index) {
                return {
                    thoi_gian: d.thoi_gian || String(index + 1),
                    khoi_luong: chuyenThanhSo(d.khoi_luong)
                };
            }).filter(function (d) {
                return d.khoi_luong !== null;
            })
        };
    });
}

function veBieuDoCanvasDonGian(canvas, ket_qua_api) {
    var ctx = canvas.getContext('2d');
    if (!ctx) return;

    var rect = canvas.getBoundingClientRect();
    var width = Math.max(320, Math.floor(rect.width || canvas.parentElement.clientWidth || 640));
    var height = Math.max(220, Math.floor(rect.height || canvas.parentElement.clientHeight || 280));
    var ty_le = window.devicePixelRatio || 1;

    canvas.width = width * ty_le;
    canvas.height = height * ty_le;
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
    ctx.setTransform(ty_le, 0, 0, ty_le, 0, 0);
    ctx.clearRect(0, 0, width, height);

    var labels = [];
    var label_da_co = {};
    ket_qua_api.forEach(function (can) {
        can.du_lieu.forEach(function (d) {
            if (!label_da_co[d.thoi_gian]) {
                label_da_co[d.thoi_gian] = true;
                labels.push(d.thoi_gian);
            }
        });
    });

    var tat_ca_gia_tri = [];
    ket_qua_api.forEach(function (can) {
        can.du_lieu.forEach(function (d) { tat_ca_gia_tri.push(d.khoi_luong); });
    });
    if (!labels.length || !tat_ca_gia_tri.length) return;

    var min_y = Math.min.apply(null, tat_ca_gia_tri);
    var max_y = Math.max.apply(null, tat_ca_gia_tri);
    if (min_y === max_y) {
        min_y = Math.max(0, min_y - 1);
        max_y = max_y + 1;
    }

    var pad = { left: 52, right: 18, top: 22, bottom: 44 };
    var plot_w = width - pad.left - pad.right;
    var plot_h = height - pad.top - pad.bottom;

    function xChoIndex(index) {
        if (labels.length === 1) return pad.left + plot_w / 2;
        return pad.left + (index / (labels.length - 1)) * plot_w;
    }
    function yChoGiaTri(value) {
        return pad.top + (1 - ((value - min_y) / (max_y - min_y))) * plot_h;
    }

    ctx.font = '11px Inter, Arial, sans-serif';
    ctx.lineWidth = 1;
    ctx.strokeStyle = '#e2e8f0';
    ctx.fillStyle = '#94a3b8';
    for (var i = 0; i <= 4; i++) {
        var y = pad.top + (plot_h / 4) * i;
        var val = max_y - ((max_y - min_y) / 4) * i;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(width - pad.right, y);
        ctx.stroke();
        ctx.fillText(val.toFixed(1) + ' kg', 6, y + 4);
    }

    var buoc_nhan = Math.max(1, Math.ceil(labels.length / 6));
    labels.forEach(function (label, index) {
        if (index % buoc_nhan !== 0 && index !== labels.length - 1) return;
        var x = xChoIndex(index);
        ctx.save();
        ctx.translate(x, height - 12);
        ctx.rotate(-0.35);
        ctx.fillText(label, -26, 0);
        ctx.restore();
    });

    ket_qua_api.forEach(function (can, chi_so) {
        var mau = MAU_CAN[chi_so % MAU_CAN.length].duong;
        var map_data = {};
        can.du_lieu.forEach(function (d) { map_data[d.thoi_gian] = d.khoi_luong; });

        ctx.beginPath();
        ctx.strokeStyle = mau;
        ctx.lineWidth = 2.5;
        var da_bat_dau = false;
        labels.forEach(function (label, index) {
            if (map_data[label] === undefined) return;
            var x = xChoIndex(index);
            var y = yChoGiaTri(map_data[label]);
            if (!da_bat_dau) {
                ctx.moveTo(x, y);
                da_bat_dau = true;
            } else {
                ctx.lineTo(x, y);
            }
        });
        ctx.stroke();

        ctx.fillStyle = mau;
        labels.forEach(function (label, index) {
            if (map_data[label] === undefined) return;
            var x = xChoIndex(index);
            var y = yChoGiaTri(map_data[label]);
            ctx.beginPath();
            ctx.arc(x, y, 3, 0, Math.PI * 2);
            ctx.fill();
        });
    });
}

// ─────────────────────────────────────────────────────────────
// Polling cap nhat du lieu can (the card)
// ─────────────────────────────────────────────────────────────
function capNhatDuLieuTrangChu() {
    var phan_tu_dl = document.getElementById('du-lieu-can-list');
    if (!phan_tu_dl) return;

    var api_url = phan_tu_dl.getAttribute('data-api-url');
    var danh_sach_can = JSON.parse(phan_tu_dl.getAttribute('data-can-list') || '[]');

    fetch(api_url, { cache: 'no-store' })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            if (!data || !Array.isArray(data.ket_qua)) return;

            var ket_noi = 0;
            data.ket_qua.forEach(function (can) {
                capNhatTheCanTrangChu(can, danh_sach_can);
                if (can.hoat_dong && chuyenThanhSo(can.khoi_luong) !== null) ket_noi++;
            });
            if (data.thong_ke) {
                var so_tong_can = document.getElementById('so-tong-can');
                var so_can_hd = document.getElementById('so-can-hoat-dong');
                var so_ban_ghi = document.getElementById('so-ban-ghi');
                if (so_tong_can) so_tong_can.textContent = data.thong_ke.tong_can;
                if (so_can_hd) so_can_hd.textContent = data.thong_ke.can_hoat_dong;
                if (so_ban_ghi) so_ban_ghi.textContent = data.thong_ke.tong_ban_ghi;
            }
            var phan_tu_kn = document.getElementById('so-dang-ket-noi');
            if (phan_tu_kn) phan_tu_kn.textContent = ket_noi;
        })
        .catch(function () {});
}

function capNhatTheCanTrangChu(can, danh_sach_can) {
    var phan_tu_kl = document.getElementById('kl-' + can.ma_can);
    var phan_tu_tg = document.getElementById('tg-' + can.ma_can);
    var phan_tu_pt = document.getElementById('pt-' + can.ma_can);
    var thanh = document.getElementById('thanh-' + can.ma_can);
    if (!phan_tu_kl) return;

    var khoi_luong = chuyenThanhSo(can.khoi_luong);

    if (khoi_luong !== null) {
        phan_tu_kl.textContent = khoi_luong.toFixed(1);
        if (phan_tu_tg) phan_tu_tg.textContent = 'Cập nhật: ' + can.thoi_gian;

        if (phan_tu_tg) phan_tu_tg.textContent = can.thoi_gian ? 'Cap nhat: ' + can.thoi_gian : 'Da co du lieu';

        var kl_toi_da = 1;
        danh_sach_can.forEach(function (c) { if (c.ma_can === can.ma_can) kl_toi_da = c.kl_toi_da; });
        kl_toi_da = chuyenThanhSo(kl_toi_da) || 1;
        var phan_tram = Math.min(100, Math.round((khoi_luong / kl_toi_da) * 1000) / 10);
        if (phan_tu_pt) phan_tu_pt.textContent = phan_tram + '%';
        if (thanh) {
            thanh.style.width = phan_tram + '%';
            if (phan_tram >= 90) thanh.classList.add('nguy-hiem');
            else thanh.classList.remove('nguy-hiem');
        }
    } else {
        phan_tu_kl.textContent = '--';
        if (phan_tu_tg) phan_tu_tg.textContent = 'Chua co du lieu';
        if (phan_tu_pt) phan_tu_pt.textContent = '0%';
        if (thanh) thanh.style.width = '0%';
    }
}

// ─────────────────────────────────────────────────────────────
// Bieu do Chart.js
// ─────────────────────────────────────────────────────────────
function taoHoacCapNhatBieuDo(ket_qua_api) {
    ket_qua_api = chuanHoaDuLieuBieuDo(ket_qua_api);
    var canvas = document.getElementById('bieu-do-khoi-luong');
    if (!canvas) return;

    // Kiem tra neu khong co du lieu gi ca
    var co_du_lieu = ket_qua_api.some(function (c) { return c.du_lieu.length > 0; });
    if (!co_du_lieu) {
        if (da_co_bieu_do) return;
        hienTrangThaiBieuDo('Chua co du lieu de ve bieu do');
        return;
    }
    da_co_bieu_do = true;
    canvas = hienCanvasBieuDo();

    // Tao labels hop nhat (toan bo nhan thoi gian)
    var tat_ca_label = {};
    ket_qua_api.forEach(function (can) {
        can.du_lieu.forEach(function (d) { tat_ca_label[d.thoi_gian] = true; });
    });
    var labels = Object.keys(tat_ca_label);

    // Tao cac dataset
    var datasets = ket_qua_api.map(function (can, chi_so) {
        var mau = MAU_CAN[chi_so % MAU_CAN.length];
        // Tao map tra cuu nhanh
        var map_data = {};
        can.du_lieu.forEach(function (d) { map_data[d.thoi_gian] = d.khoi_luong; });

        return {
            label: can.ten_can + ' (' + can.ma_can + ')',
            data: labels.map(function (l) { return map_data[l] !== undefined ? map_data[l] : null; }),
            borderColor: mau.duong,
            backgroundColor: mau.nen,
            borderWidth: 2.5,
            pointRadius: 3,
            pointHoverRadius: 6,
            pointBackgroundColor: mau.duong,
            tension: 0.4,
            fill: true,
            spanGaps: true,
        };
    });

    // Cau hinh bieu do
    var cau_hinh = {
        type: 'line',
        data: { labels: labels, datasets: datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: { color: '#475569', font: { size: 12, weight: '600', family: 'Inter' }, usePointStyle: true, padding: 20 }
                },
                tooltip: {
                    backgroundColor: '#fff',
                    titleColor: '#0f172a',
                    bodyColor: '#475569',
                    borderColor: '#e2e8f0',
                    borderWidth: 1,
                    padding: 12,
                    callbacks: {
                        label: function (ctx) {
                            return ' ' + ctx.dataset.label + ': ' + (ctx.parsed.y !== null ? ctx.parsed.y.toFixed(2) + ' kg' : 'N/A');
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: '#f1f5f9', lineWidth: 1 },
                    ticks: { color: '#94a3b8', font: { size: 11, family: 'Inter' }, maxTicksLimit: 10, maxRotation: 30 },
                    border: { color: '#e2e8f0' }
                },
                y: {
                    grid: { color: '#f1f5f9', lineWidth: 1 },
                    ticks: {
                        color: '#94a3b8', font: { size: 11, family: 'Inter' },
                        callback: function (val) { return val + ' kg'; }
                    },
                    border: { color: '#e2e8f0' }
                }
            }
        }
    };

    if (typeof Chart === 'undefined') {
        veBieuDoCanvasDonGian(canvas, ket_qua_api);
    } else if (doi_tuong_bieu_do) {
        // Cap nhat du lieu thay vi tao lai
        doi_tuong_bieu_do.data.labels = labels;
        doi_tuong_bieu_do.data.datasets = datasets;
        doi_tuong_bieu_do.update('none');
    } else {
        doi_tuong_bieu_do = new Chart(canvas, cau_hinh);
    }

    // Cap nhat chu thich
    var chu_thich = document.getElementById('chu-thich-bieu-do');
    if (chu_thich) {
        var tong_diem = ket_qua_api.reduce(function (s, c) { return s + c.du_lieu.length; }, 0);
        chu_thich.textContent = tong_diem + ' điểm dữ liệu · 50 bản ghi gần nhất mỗi cân';
    }
}

function capNhatBieuDo() {
    var phan_tu_dl = document.getElementById('du-lieu-can-list');
    if (!phan_tu_dl) return;

    var api_url = phan_tu_dl.getAttribute('data-api-bieu-do');
    fetch(api_url, { cache: 'no-store' })
        .then(function (res) { return res.json(); })
        .then(function (data) { taoHoacCapNhatBieuDo(data ? data.ket_qua : []); })
        .catch(function () {
            if (!da_co_bieu_do) hienTrangThaiBieuDo('Khong tai duoc du lieu bieu do');
        });
}

function layBieuDoBanDau() {
    var script = document.getElementById('du-lieu-bieu-do-ban-dau');
    if (!script || !script.textContent) return [];
    try {
        return JSON.parse(script.textContent);
    } catch (e) {
        return [];
    }
}

// ─────────────────────────────────────────────────────────────
// Bang lich su tong hop
// ─────────────────────────────────────────────────────────────
function capNhatLichSuChung() {
    var phan_tu_dl = document.getElementById('du-lieu-can-list');
    if (!phan_tu_dl) return;

    var api_url = phan_tu_dl.getAttribute('data-api-lich-su');
    fetch(api_url, { cache: 'no-store' })
        .then(function (res) { return res.json(); })
        .then(function (data) { hienThiBangLichSuChung(data.ban_ghi); })
        .catch(function () {});
}

function hienThiBangLichSuChung(ban_ghi_list) {
    var body = document.getElementById('body-lich-su-chung');
    var dem = document.getElementById('dem-ban-ghi');
    if (!body) return;

    if (!ban_ghi_list || ban_ghi_list.length === 0) {
        body.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--mau-chu-mo);padding:32px">Chưa có bản ghi nào</td></tr>';
        return;
    }

    if (dem) dem.textContent = ban_ghi_list.length + ' bản ghi mới nhất';

    var html = '';
    ban_ghi_list.forEach(function (b, chi_so) {
        html += '<tr>';
        html += '<td style="color:var(--mau-chu-mo);font-size:12px">' + (chi_so + 1) + '</td>';
        html += '<td><span class="tag-can">' + b.ma_can + '</span> <span style="font-size:12px;color:var(--mau-chu-mo)">' + b.ten_can + '</span></td>';
        html += '<td style="font-weight:700;color:var(--mau-chinh)">' + parseFloat(b.khoi_luong).toFixed(2) + ' kg</td>';
        html += '<td style="font-size:12px;color:var(--mau-chu-mo)">' + b.thoi_gian + '</td>';
        html += '<td>';
        if (b.anh) {
            html += '<img src="' + b.anh + '" class="anh-nho-chung" data-url="' + b.anh + '" alt="anh">';
        } else {
            html += '<span style="color:var(--mau-chu-min)">—</span>';
        }
        html += '</td>';
        html += '</tr>';
    });
    body.innerHTML = html;

    // Gan su kien click anh
    body.querySelectorAll('.anh-nho-chung').forEach(function (anh) {
        anh.addEventListener('click', function () {
            var modal = document.getElementById('modal-anh-trang-chu');
            var img = document.getElementById('anh-phong-to-trang-chu');
            if (modal && img) { img.src = this.getAttribute('data-url'); modal.classList.add('hien'); }
        });
    });
}

// ─────────────────────────────────────────────────────────────
// Khoi dong khi trang tai xong
// ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {

    // ── Hamburger menu mobile ──
    var hamburger = document.getElementById('hamburger-btn');
    var menu = document.getElementById('navbar-menu');
    if (hamburger && menu) {
        hamburger.addEventListener('click', function () {
            hamburger.classList.toggle('open');
            menu.classList.toggle('mo');
        });
        // Dong menu khi click ngoai
        document.addEventListener('click', function (e) {
            if (!hamburger.contains(e.target) && !menu.contains(e.target)) {
                hamburger.classList.remove('open');
                menu.classList.remove('mo');
            }
        });
        // Dong menu khi click vao link trong menu
        menu.querySelectorAll('a').forEach(function(link) {
            link.addEventListener('click', function() {
                hamburger.classList.remove('open');
                menu.classList.remove('mo');
            });
        });
    }

    // ── Popup thong tin ca nhan ──
    var btn_mo_profile = document.getElementById('btn-mo-profile');
    var btn_mo_profile_mobile = document.getElementById('btn-mo-profile-mobile');
    var modal_ca_nhan = document.getElementById('modal-ca-nhan');
    var btn_dong_ca_nhan = document.getElementById('btn-dong-ca-nhan');
    var btn_luu_ca_nhan = document.getElementById('btn-luu-ca-nhan');
    var api_ca_nhan = '/api/ca-nhan/';

    if (btn_mo_profile && modal_ca_nhan) {
        btn_mo_profile.addEventListener('click', function () {
            modal_ca_nhan.classList.add('hien');
        });
    }
    if (btn_mo_profile_mobile && modal_ca_nhan) {
        btn_mo_profile_mobile.addEventListener('click', function (e) {
            e.preventDefault();
            modal_ca_nhan.classList.add('hien');
            var hamburger = document.getElementById('hamburger-btn');
            var menu = document.getElementById('navbar-menu');
            if(hamburger && menu) {
                hamburger.classList.remove('open');
                menu.classList.remove('mo');
            }
        });
    }
    if (modal_ca_nhan) {
        modal_ca_nhan.addEventListener('click', function (e) {
            if (e.target === modal_ca_nhan) modal_ca_nhan.classList.remove('hien');
        });
    }
    if (btn_dong_ca_nhan) btn_dong_ca_nhan.addEventListener('click', function () {
        if (modal_ca_nhan) modal_ca_nhan.classList.remove('hien');
    });
    if (btn_luu_ca_nhan) btn_luu_ca_nhan.addEventListener('click', function () {
        var ho_ten = (document.getElementById('ca-nhan-ho-ten') || {}).value || '';
        var email = (document.getElementById('ca-nhan-email') || {}).value || '';
        var mk_cu = (document.getElementById('ca-nhan-mk-cu') || {}).value || '';
        var mk_moi = (document.getElementById('ca-nhan-mk-moi') || {}).value || '';
        window.guiPost(api_ca_nhan, {
            ho_ten: ho_ten, email: email, mat_khau_cu: mk_cu, mat_khau_moi: mk_moi
        }, function () {
            window.hienThiThongBao('Đã cập nhật thông tin cá nhân', 'thanh-cong');
            if (modal_ca_nhan) modal_ca_nhan.classList.remove('hien');
            if (mk_moi) {
                window.hienThiThongBao('Mật khẩu đã đổi. Vui lòng đăng nhập lại', 'canh-bao');
                setTimeout(function () { location.href = '/dang-xuat/'; }, 2000);
            }
        });
    });

    // ── Nut cuon len tren cung ──
    var btnCuonLen = document.getElementById('btn-cuon-len');
    if (btnCuonLen) {
        window.addEventListener('scroll', function() {
            if (window.scrollY > 200) {
                btnCuonLen.classList.add('hien');
            } else {
                btnCuonLen.classList.remove('hien');
            }
        });
        btnCuonLen.addEventListener('click', function() {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }

    if (!document.getElementById('du-lieu-can-list')) return;

    // Dong modal anh
    var modal_anh = document.getElementById('modal-anh-trang-chu');
    if (modal_anh) {
        modal_anh.addEventListener('click', function (e) {
            if (e.target === modal_anh) modal_anh.classList.remove('hien');
        });
    }

    // Chay ngay lan dau
    capNhatDuLieuTrangChu();
    taoHoacCapNhatBieuDo(layBieuDoBanDau());
    capNhatBieuDo();
    capNhatLichSuChung();

    // Polling dinh ky
    setInterval(capNhatDuLieuTrangChu, KHOANG_CACH);
    setInterval(capNhatBieuDo, KHOANG_CACH);
    setInterval(capNhatLichSuChung, KHOANG_CACH);
});
