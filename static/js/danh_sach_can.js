/**
 * Cap nhat danh sach can moi 5 giay, khong reload trang.
 */

var KHOANG_CACH_DANH_SACH_CAN = 5000;

function capNhatDanhSachCan() {
    var dl = document.getElementById('du-lieu-trang');
    if (!dl) return;

    var api_url = dl.getAttribute('data-api-tat-ca');
    var danh_sach_can = JSON.parse(dl.getAttribute('data-can-list') || '[]');
    if (!api_url) return;

    fetch(api_url, { cache: 'no-store' })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            if (!data.ket_qua) return;
            data.ket_qua.forEach(function (can) {
                capNhatTheCanDanhSach(can, danh_sach_can);
            });
        })
        .catch(function () {});
}

function capNhatTheCanDanhSach(can, danh_sach_can) {
    var phan_tu_kl = document.getElementById('kl-ds-' + can.ma_can);
    var phan_tu_tg = document.getElementById('tg-ds-' + can.ma_can);
    if (!phan_tu_kl) return;

    if (can.khoi_luong === null || can.khoi_luong === undefined) {
        phan_tu_kl.innerHTML = '<span class="chua-co">--</span>';
        if (phan_tu_tg) phan_tu_tg.textContent = 'Chua co du lieu';
        return;
    }

    phan_tu_kl.textContent = parseFloat(can.khoi_luong).toFixed(1);
    if (phan_tu_tg) phan_tu_tg.textContent = 'Cap nhat: ' + can.thoi_gian;

    var kl_toi_da = 0;
    danh_sach_can.forEach(function (item) {
        if (item.ma_can === can.ma_can) kl_toi_da = parseFloat(item.kl_toi_da) || 0;
    });

    if (kl_toi_da > 0) {
        var phan_tram = Math.min(100, (parseFloat(can.khoi_luong) / kl_toi_da) * 100);
        var thanh = document.getElementById('thanh-ds-' + can.ma_can);
        var pt = document.getElementById('pt-ds-' + can.ma_can);
        if (thanh) thanh.style.width = phan_tram.toFixed(1) + '%';
        if (pt) pt.textContent = phan_tram.toFixed(1) + '%';
    }
}

document.addEventListener('DOMContentLoaded', function () {
    capNhatDanhSachCan();
    setInterval(capNhatDanhSachCan, KHOANG_CACH_DANH_SACH_CAN);
});
