/**
 * quan_ly.js - Gian don, de hieu
 * Xu ly 2 trang: Nguoi dung va Phan quyen
 */

// ═══════════════════════════════════════════════════
// TIEN ICH CHUNG
// ═══════════════════════════════════════════════════

// Mo / dong modal
function moModal(id) { document.getElementById(id).classList.add('hien'); }
function dongModal(id) { document.getElementById(id).classList.remove('hien'); }

// Lay / dat gia tri o nhap
function lay(id) { return document.getElementById(id).value.trim(); }
function dat(id, val) { document.getElementById(id).value = val || ''; }

// Dong modal khi click ra ngoai (vung overlay)
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('hien');
    }
});

// ═══════════════════════════════════════════════════
// CUSTOM CONFIRM DIALOG
// ═══════════════════════════════════════════════════

/**
 * xacNhan(tuyChon, callback)
 * Thay the window.confirm() bang dialog dep hon.
 * tuyChon: { icon, tieu_de, noi_dung, nhan_xac_nhan, loai }
 *   loai: 'loai-khoa' | 'loai-mo-khoa' | 'loai-cap-admin' | 'loai-bo-admin'
 */
function xacNhan(tuyChon, callback) {
    // Xoa dialog cu neu co
    var cu = document.getElementById('_confirm-overlay');
    if (cu) cu.remove();

    var overlay = document.createElement('div');
    overlay.id = '_confirm-overlay';
    overlay.className = 'confirm-overlay';
    overlay.innerHTML =
        '<div class="confirm-box ' + (tuyChon.loai || '') + '">'
        + '<div class="confirm-icon">' + (tuyChon.icon || '❓') + '</div>'
        + '<div class="confirm-tieu-de">' + (tuyChon.tieu_de || 'Xác nhận') + '</div>'
        + '<div class="confirm-noi-dung">' + (tuyChon.noi_dung || '') + '</div>'
        + '<div class="confirm-actions">'
        + '<button class="btn-xac-nhan" id="_confirm-ok">' + (tuyChon.nhan_xac_nhan || 'Đồng ý') + '</button>'
        + '<button class="btn-huy" id="_confirm-huy">Đồng ý</button>'
        + '</div></div>';

    // Nut huy: Van ban theo ngu canh
    overlay.querySelector('#_confirm-huy').textContent = tuyChon.nhan_huy || 'Hủy';

    document.body.appendChild(overlay);

    // Kich hoat animation
    requestAnimationFrame(function() { overlay.classList.add('hien'); });

    function dongDialog() {
        overlay.classList.remove('hien');
        setTimeout(function() { overlay.remove(); }, 250);
    }

    overlay.querySelector('#_confirm-ok').onclick = function() {
        dongDialog();
        callback(true);
    };
    overlay.querySelector('#_confirm-huy').onclick = function() {
        dongDialog();
        callback(false);
    };
    // Click ben ngoai box de huy
    overlay.onclick = function(e) {
        if (e.target === overlay) { dongDialog(); callback(false); }
    };
    // Phim ESC de huy
    function xuLyEsc(e) {
        if (e.key === 'Escape') { document.removeEventListener('keydown', xuLyEsc); dongDialog(); callback(false); }
    }
    document.addEventListener('keydown', xuLyEsc);
}

// ═══════════════════════════════════════════════════
// DROPDOWN - Dung position:fixed de tranh bi cat
// ═══════════════════════════════════════════════════

document.addEventListener('click', function(e) {
    var toggle = e.target.closest('.dropdown-toggle');

    if (toggle) {
        // Ngan lan bubot len de khong bi dong ngay
        e.stopPropagation();

        var menu = toggle.closest('.dropdown').querySelector('.dropdown-menu');
        var dangMo = menu.classList.contains('hien');

        // Dong tat ca dropdown dang mo
        document.querySelectorAll('.dropdown-menu.hien').forEach(function(m) {
            m.classList.remove('hien');
        });

        if (!dangMo) {
            // Tinh vi tri fixed tuong doi voi viewport
            var vitri = toggle.getBoundingClientRect();
            menu.classList.add('hien');
        }
        return;
    }

    // Click ngoai -> dong tat ca
    document.querySelectorAll('.dropdown-menu.hien').forEach(function(m) {
        m.classList.remove('hien');
    });
});

// ═══════════════════════════════════════════════════
// KHOI DONG KHI TRANG TAI XONG
// ═══════════════════════════════════════════════════

var ID_THAO_TAC = null; // Luu id nguoi dung dang thao tac

document.addEventListener('DOMContentLoaded', function() {
    var trang = document.getElementById('du-lieu-trang');
    if (!trang) return;

    if (trang.getAttribute('data-api-tao')) {
        khoidongTrangNguoiDung(trang);
    } else {
        khoidongTrangPhanQuyen(trang);
    }
});

// ═══════════════════════════════════════════════════
// TRANG QUAN LY NGUOI DUNG
// ═══════════════════════════════════════════════════

function khoidongTrangNguoiDung(trang) {
    var API_TAO = trang.getAttribute('data-api-tao');

    // Nut tao tai khoan
    document.getElementById('btn-mo-modal-tao-tk').onclick  = function() { moModal('modal-tao-tk'); };
    document.getElementById('btn-dong-modal-tao-tk').onclick = function() { dongModal('modal-tao-tk'); };
    document.getElementById('btn-luu-tai-khoan').onclick     = function() { taoTaiKhoan(API_TAO); };

    // Nut sua tai khoan
    document.getElementById('btn-dong-sua-tk').onclick = function() { dongModal('modal-sua-tk'); };
    document.getElementById('btn-luu-sua-tk').onclick  = luuSuaTaiKhoan;

    // Nut reset mat khau
    document.getElementById('btn-dong-reset-mk').onclick = function() { dongModal('modal-reset-mk'); };
    document.getElementById('btn-luu-reset-mk').onclick  = luuResetMatKhau;

    // Xu ly click trong bang qua event delegation
    var bang = document.getElementById('bang-nguoi-dung');
    if (!bang) return;

    bang.addEventListener('click', function(e) {
        // Dong dropdown khi chon 1 item
        if (e.target.closest('.dropdown-item')) {
            document.querySelectorAll('.dropdown-menu.hien').forEach(function(m) { m.classList.remove('hien'); });
        }

        var btn = e.target.closest('button[class*="btn-"]');
        if (!btn) return;

        if (btn.classList.contains('btn-sua'))     return moModalSua(btn);
        if (btn.classList.contains('btn-reset-mk')) return moModalReset(btn);
        if (btn.classList.contains('btn-khoa'))    return thucHienKhoa(btn);
        if (btn.classList.contains('btn-admin'))   return thucHienCapAdmin(btn);
        if (btn.classList.contains('btn-xoa-nd')) return thucHienXoa(btn);
    });

    // Tim kiem
    khoidongTimKiemNguoiDung();
}


// ─── Tao tai khoan ─────────────────────────────────
function taoTaiKhoan(url) {
    var ten   = lay('inp-ten-dang-nhap');
    var mk    = lay('inp-mat-khau');
    var mk_check    = lay('inp-mat-khau-check');
    var ho    = lay('inp-ho-ten');
    var email = lay('inp-email');
    var is_admin = document.getElementById('inp-is-admin').checked;

    if (!ten || !mk) {
        window.hienThiThongBao('Vui lòng nhập tên đăng nhập và mật khẩu', 'canh-bao');
        return;
    }
    if (mk !== mk_check) {
        window.hienThiThongBao('Mật khẩu không khớp', 'canh-bao');
        return;
    }

    window.guiPost(url, { ten_dang_nhap: ten, mat_khau: mk, mat_khau_check: mk_check, ho_ten: ho, email: email, is_admin: is_admin, nhom_ids: [] },
        function(kq) {
            window.hienThiThongBao('Đã tạo tài khoản: ' + kq.ten, 'thanh-cong');
            dongModal('modal-tao-tk');
            setTimeout(function() { location.reload(); }, 1200);
        }
    );
}

// ─── Sua tai khoan ─────────────────────────────────
function moModalSua(btn) {
    ID_THAO_TAC = +btn.dataset.ndId;
    document.getElementById('tieu-de-modal-sua').textContent = '✏️ Sửa: ' + btn.dataset.ndTen;
    dat('sua-ho-ten', btn.dataset.ndHo);
    dat('sua-email', btn.dataset.ndEmail);
    moModal('modal-sua-tk');
}

function luuSuaTaiKhoan() {
    if (!ID_THAO_TAC) return;
    window.guiPost('/api/quan-ly/nguoi-dung/' + ID_THAO_TAC + '/sua/', {
        ho_ten: lay('sua-ho-ten'),
        email: lay('sua-email')
    }, function() {
        window.hienThiThongBao('Đã cập nhật thông tin', 'thanh-cong');
        dongModal('modal-sua-tk');
        setTimeout(function() { location.reload(); }, 1000);
    });
}

// ─── Reset mat khau ────────────────────────────────
function moModalReset(btn) {
    ID_THAO_TAC = +btn.dataset.ndId;
    document.getElementById('tieu-de-modal-reset').textContent = '🔑 Reset MK: ' + btn.dataset.ndTen;
    dat('reset-mat-khau-moi', '');
    moModal('modal-reset-mk');
}

function luuResetMatKhau() {
    if (!ID_THAO_TAC) return;
    var mk = lay('reset-mat-khau-moi');
    if (mk.length < 6) {
        window.hienThiThongBao('Mật khẩu phải từ 6 ký tự', 'canh-bao');
        return;
    }
    window.guiPost('/api/quan-ly/nguoi-dung/' + ID_THAO_TAC + '/reset-mk/', { mat_khau_moi: mk },
        function() {
            window.hienThiThongBao('Đã đặt lại mật khẩu', 'thanh-cong');
            dongModal('modal-reset-mk');
        }
    );
}

// ─── Khoa / Mo khoa ────────────────────────────────
function thucHienKhoa(btn) {
    var id = +btn.dataset.ndId;
    var ten = btn.dataset.ndTen;
    var dangKhoa = btn.dataset.dangKhoa === 'true';

    xacNhan({
        icon: dangKhoa ? '🔓' : '🔒',
        tieu_de: (dangKhoa ? 'Mở khóa tài khoản' : 'Khóa tài khoản'),
        noi_dung: (dangKhoa
            ? 'Tài khoản <strong>' + ten + '</strong> sẽ được mở khóa và có thể đăng nhập trở lại.'
            : 'Tài khoản <strong>' + ten + '</strong> sẽ bị khóa và không thể đăng nhập.'),
        nhan_xac_nhan: dangKhoa ? '🔓 Mở khóa' : '🔒 Khóa',
        nhan_huy: 'Hủy',
        loai: dangKhoa ? 'loai-mo-khoa' : 'loai-khoa'
    }, function(dongY) {
        if (!dongY) return;

    window.guiPost('/api/quan-ly/nguoi-dung/' + id + '/khoa/', {}, function(kq) {
        var badge = document.getElementById('status-badge-' + id);
        var hang  = document.getElementById('hang-nd-' + id);

        if (kq.dang_khoa) {
            badge.className   = 'badge badge-do';
            badge.textContent = '🔒 Bị khóa';
            btn.textContent        = '🔓 Mở khóa';
            btn.dataset.dangKhoa   = 'true';
        } else {
            badge.className   = 'badge badge-xanh-la';
            badge.textContent = '🟢 Hoạt động';
            btn.textContent        = '🔒 Khóa tài khoản';
            btn.dataset.dangKhoa   = 'false';
        }
        window.hienThiThongBao((kq.dang_khoa ? 'Đã khóa' : 'Đã mở khóa') + ': ' + ten, 'thanh-cong');
    });
    }); // ket thuc xacNhan
}

// ─── Cap / Bo admin ────────────────────────────────
function thucHienCapAdmin(btn) {
    var id = +btn.dataset.ndId;
    var ten = btn.dataset.ndTen;
    var laAdmin = btn.dataset.laAdmin === 'true';

    xacNhan({
        icon: laAdmin ? '⬇️' : '⬆️',
        tieu_de: (laAdmin ? 'Bỏ quyền Admin' : 'Cấp quyền Admin'),
        noi_dung: (laAdmin
            ? 'Bỏ quyền quản trị của <strong>' + ten + '</strong>?'
            : 'Cấp quyền quản trị cho <strong>' + ten + '</strong>?'),
        nhan_xac_nhan: laAdmin ? '👤 Bỏ Admin' : '👑 Cấp Admin',
        nhan_huy: 'Hủy',
        loai: laAdmin ? 'loai-bo-admin' : 'loai-cap-admin'
    }, function(dongY) {
        if (!dongY) return;

    window.guiPost('/api/quan-ly/nguoi-dung/' + id + '/admin/', {}, function(kq) {
        var badge = document.getElementById('role-badge-' + id);
        if (kq.la_admin) {
            badge.className   = 'badge badge-xanh';
            badge.textContent = '🔧 Admin';
            btn.textContent     = '👤 Bỏ Admin';
            btn.dataset.laAdmin = 'true';
        } else {
            badge.className   = 'badge';
            badge.textContent = '👤 Người dùng';
            btn.textContent     = '👑 Cấp Admin';
            btn.dataset.laAdmin = 'false';
        }
        window.hienThiThongBao((kq.la_admin ? 'Đã cấp' : 'Đã bỏ') + ' Admin: ' + ten, 'thanh-cong');
    });
    }); // ket thuc xacNhan
}

// ─── Xoa tai khoan ─────────────────────────────────
function thucHienXoa(btn) {
    var id = +btn.dataset.ndId;
    var ten = btn.dataset.ndTen;

    xacNhan({
        icon: '🗑️',
        tieu_de: 'Xóa tài khoản',
        noi_dung: 'Bạn có chắc muốn xóa tài khoản <strong>' + ten + '</strong>? Hành động này không thể hoàn tác.',
        nhan_xac_nhan: '🗑️ Xóa',
        nhan_huy: 'Hủy',
        loai: 'loai-khoa'
    }, function(dongY) {
        if (!dongY) return;

    window.guiPost('/api/quan-ly/xoa-tai-khoan/' + id + '/', {}, function() {
        var hang = document.getElementById('hang-nd-' + id);
        hang.style.opacity    = '0';
        hang.style.transition = 'opacity 0.4s';
        setTimeout(function() { hang.remove(); }, 500);
        window.hienThiThongBao('Đã xóa tài khoản: ' + ten, 'thanh-cong');
    });
    }); // ket thuc xacNhan
}

// ═══════════════════════════════════════════════════
// TRANG PHAN QUYEN
// ═══════════════════════════════════════════════════

function khoidongTrangPhanQuyen(trang) {
    var NHOM_LIST = JSON.parse(trang.getAttribute('data-nhom-list') || '[]');
    var ID_USER = null; // User dang duoc phan quyen

    // Dong modal
    document.getElementById('btn-dong-pq').onclick = function() { dongModal('modal-phan-quyen'); };

    // Luu phan quyen
    document.getElementById('btn-luu-pq').onclick = function() {
        if (!ID_USER) return;

        var nhomIds = [];
        document.querySelectorAll('#danh-sach-check-nhom input:checked').forEach(function(cb) {
            nhomIds.push(+cb.value);
        });

        window.guiPost('/api/quan-ly/nguoi-dung/' + ID_USER + '/nhom/', { nhom_ids: nhomIds }, function() {
            window.hienThiThongBao('Đã lưu phân quyền', 'thanh-cong');
            dongModal('modal-phan-quyen');

            // Cap nhat tags hien thi tren bang
            var khu = document.getElementById('nhom-tags-' + ID_USER);
            if (khu) {
                var html = nhomIds.map(function(id) {
                    var nhom = NHOM_LIST.find(function(n) { return n.id === id; });
                    return nhom ? '<span class="tag-nhom">' + nhom.ten + '</span>' : '';
                }).join('');
                khu.innerHTML = html || '<span class="chua-co-quyen">Chưa phân quyền</span>';
            }

            // Luu lai nhom-ids vao nut de lan sau mo dung
            var btn = document.querySelector('.btn-mo-phan-quyen[data-nd-id="' + ID_USER + '"]');
            if (btn) btn.dataset.nhomIds = nhomIds.join(',');
        });
    };

    // Mo modal phan quyen khi click nut
    document.addEventListener('click', function(e) {
        var btn = e.target.closest('.btn-mo-phan-quyen');
        if (!btn) return;

        ID_USER = +btn.dataset.ndId;
        var nhomIdsCu = (btn.dataset.nhomIds || '').split(',').map(Number).filter(Boolean);

        // Cap nhat tieu de modal
        document.getElementById('tieu-de-modal-pq').textContent = '⚙️ Phân quyền: ' + btn.dataset.ndTen;

        // Render danh sach checkbox nhom
        var khu = document.getElementById('danh-sach-check-nhom');
        if (NHOM_LIST.length === 0) {
            khu.innerHTML = '<p style="color:var(--mau-chu-mo);padding:10px 0">Chưa có nhóm nào. Tạo nhóm qua Django Admin.</p>';
        } else {
            khu.innerHTML = NHOM_LIST.map(function(nh) {
                var checked = nhomIdsCu.indexOf(nh.id) !== -1 ? 'checked' : '';
                return '<label class="hang-quyen-check">'
                     + '<input type="checkbox" value="' + nh.id + '" ' + checked + '>'
                     + '<span>' + nh.ten + '</span>'
                     + '</label>';
            }).join('');
        }

        moModal('modal-phan-quyen');
    });

    // Tim kiem
    khoidongTimKiemPhanQuyen();
}

// ═══════════════════════════════════════════════════
// TIM KIEM CLIENT-SIDE
// ═══════════════════════════════════════════════════

/**
 * Loc bang theo tu khoa.
 * Moi hang phai co data-tim="..." chua cac text de tim.
 * Khi khong tim thay --> hien hang #hang-khong-tim-{id}.
 */
function locBang(inputEl, btnXoa, selHangDuLieu, hangKhongTimThay, callbackCapNhat) {
    function capNhat() {
        var tuKhoa = inputEl.value.trim().toLowerCase();

        // Hien / an nut xoa
        if (tuKhoa) {
            btnXoa.classList.add('hien');
        } else {
            btnXoa.classList.remove('hien');
        }

        var coDuLieu = false;
        var soDuLieuHien = 0;
        document.querySelectorAll(selHangDuLieu).forEach(function(hang) {
            var van_ban = (hang.getAttribute('data-tim') || hang.textContent).toLowerCase();
            var hien = !tuKhoa || van_ban.indexOf(tuKhoa) !== -1;
            hang.style.display = hien ? '' : 'none';
            if (hien) {
                coDuLieu = true;
                soDuLieuHien++;
            }
        });

        // Hien / an hang "khong tim thay"
        if (hangKhongTimThay) {
            hangKhongTimThay.classList.toggle('hien', tuKhoa && !coDuLieu);
        }

        // Goi callback de cap nhat so luong neu co
        if (callbackCapNhat) {
            callbackCapNhat(soDuLieuHien);
        }
    }

    inputEl.addEventListener('input', capNhat);
    btnXoa.addEventListener('click', function() {
        inputEl.value = '';
        inputEl.focus();
        capNhat();
    });

    // Phim ESC de xoa
    inputEl.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') { inputEl.value = ''; capNhat(); }
    });
}

// ─── Tim kiem trang Nguoi dung ────────────────────────────────────
function khoidongTimKiemNguoiDung() {
    var inp    = document.getElementById('inp-tim-nguoi-dung');
    var btnXoa = document.getElementById('btn-xoa-tim-nd');
    var khong  = document.getElementById('hang-khong-tim-nd');
    if (!inp || !btnXoa) return;

    // Gan data-tim cho moi hang de loc nhanh
    document.querySelectorAll('#bang-nguoi-dung tbody tr[id^="hang-nd-"]').forEach(function(hang) {
        var ten   = (hang.querySelector('.ten')    || {}).textContent || '';
        var hoTen = (hang.querySelector('.ho-ten') || {}).textContent || '';
        var email = (hang.querySelector('.col-email') ? hang.querySelector('td.col-email') : null);
        var emailTxt = email ? email.textContent : '';
        hang.setAttribute('data-tim', (ten + ' ' + hoTen + ' ' + emailTxt).toLowerCase());
    });

    // Callback de cap nhat so luong
    function capNhatSoLuong(so) {
        // Tim phan tu hien thi so tong cong tren header
        var headerDiv = document.querySelector('.ql-header > div:first-child strong');
        if (headerDiv) {
            headerDiv.textContent = so;
        }
    }

    locBang(inp, btnXoa, '#bang-nguoi-dung tbody tr[id^="hang-nd-"]', khong, capNhatSoLuong);
}

// ─── Tim kiem trang Phan quyen ────────────────────────────────────
function khoidongTimKiemPhanQuyen() {
    var inp    = document.getElementById('inp-tim-phan-quyen');
    var btnXoa = document.getElementById('btn-xoa-tim-pq');
    var khong  = document.getElementById('hang-khong-tim-pq');
    if (!inp || !btnXoa) return;

    // Gan data-tim cho moi hang
    document.querySelectorAll('tr[id^="hang-pq-"]').forEach(function(hang) {
        hang.setAttribute('data-tim', hang.textContent.toLowerCase());
    });

    // Callback de cap nhat so luong
    function capNhatSoLuong(so) {
        var spanDem = document.getElementById('dem-tai-khoan-pq');
        if (spanDem) {
            spanDem.textContent = so + ' tài khoản';
        }
    }

    locBang(inp, btnXoa, 'tr[id^="hang-pq-"]', khong, capNhatSoLuong);
}
