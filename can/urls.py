from django.urls import path
from . import views

urlpatterns = [
    # ─── Xac thuc ───────────────────────────────────────────
    path('dang-nhap/', views.trang_dang_nhap, name='trang_dang_nhap'),
    path('dang-xuat/', views.trang_dang_xuat, name='trang_dang_xuat'),

    # ─── Trang chinh ────────────────────────────────────────
    path('', views.trang_chu, name='trang_chu'),

    # ─── Can ────────────────────────────────────────────────
    path('can/', views.danh_sach_can, name='danh_sach_can'),
    path('can/<str:ma_can>/', views.chi_tiet_can, name='chi_tiet_can'),
    path('api/can/<str:ma_can>/sua/', views.api_sua_can, name='api_sua_can'),

    # ─── Quan ly ────────────────────────────────────────────
    path('quan-ly/nguoi-dung/', views.quan_ly_nguoi_dung, name='quan_ly_nguoi_dung'),
    path('quan-ly/nhom-quyen/', views.quan_ly_nhom_quyen, name='quan_ly_nhom_quyen'),

    # ─── API noi bo (JSON cho JS polling) ───────────────────
    path('api/can/tat-ca/', views.api_tat_ca_can, name='api_tat_ca_can'),
    path('api/can/<str:ma_can>/du-lieu/', views.api_du_lieu_can, name='api_du_lieu_can'),
    path('api/can/<str:ma_can>/nhan-dien-trong-luong/', views.api_nhan_dien_trong_luong_can, name='api_nhan_dien_trong_luong_can'),
    path('api/can/<str:ma_can>/lich-su/', views.api_lich_su_can, name='api_lich_su_can'),

    # ─── API trang chu: bieu do + lich su tong hop ──────────
    path('api/trang-chu/bieu-do/', views.api_bieu_do_trang_chu, name='api_bieu_do_trang_chu'),
    path('api/trang-chu/lich-su/', views.api_lich_su_trang_chu, name='api_lich_su_trang_chu'),
    path('api/webrtc/http-proxy/', views.api_webrtc_http_proxy, name='api_webrtc_http_proxy'),

    # Xem camera
    path('xem-camera/', views.xem_camera, name='xem_camera'),
    path('can/<str:ma_can>/xem-camera/', views.xem_camera, name='xem_camera_can'),


    # ─── API quan ly nguoi dung (AJAX) ──────────────────────
    path('api/quan-ly/tao-tai-khoan/', views.api_tao_tai_khoan, name='api_tao_tai_khoan'),
    path('api/quan-ly/xoa-tai-khoan/<int:nguoi_dung_id>/', views.api_xoa_tai_khoan, name='api_xoa_tai_khoan'),
    path('api/quan-ly/nguoi-dung/<int:nguoi_dung_id>/nhom/', views.api_cap_nhat_nhom_nguoi_dung, name='api_cap_nhat_nhom_nguoi_dung'),


    # ─── API tai khoan (AJAX) - Them moi ────────────────────
    path('api/quan-ly/nguoi-dung/<int:nguoi_dung_id>/sua/', views.api_sua_tai_khoan, name='api_sua_tai_khoan'),
    path('api/quan-ly/nguoi-dung/<int:nguoi_dung_id>/khoa/', views.api_khoa_tai_khoan, name='api_khoa_tai_khoan'),
    path('api/quan-ly/nguoi-dung/<int:nguoi_dung_id>/reset-mk/', views.api_reset_mat_khau, name='api_reset_mat_khau'),
    path('api/quan-ly/nguoi-dung/<int:nguoi_dung_id>/admin/', views.api_cap_quyen_admin, name='api_cap_quyen_admin'),
    path('api/ca-nhan/', views.api_cap_nhat_ca_nhan, name='api_cap_nhat_ca_nhan'),
]
