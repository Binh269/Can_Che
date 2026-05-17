from django.contrib import admin
from .models import Can, Camera, BanGhiCan


class CameraInline(admin.TabularInline):
    model = Camera
    extra = 1


@admin.register(Can)
class CanAdmin(admin.ModelAdmin):
    list_display = ['ma_can', 'ten_can', 'vi_tri', 'hang', 'khoi_luong_toi_da', 'hoat_dong']
    list_filter = ['hoat_dong', 'hang']
    search_fields = ['ma_can', 'ten_can', 'vi_tri']
    inlines = [CameraInline]


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ['id', 'ten_camera', 'can', 'hoat_dong']
    list_filter = ['hoat_dong']


@admin.register(BanGhiCan)
class BanGhiCanAdmin(admin.ModelAdmin):
    list_display = ['id', 'can', 'khoi_luong', 'thoi_gian']
    list_filter = ['can']
    readonly_fields = ['du_lieu_goc']
    date_hierarchy = 'thoi_gian'
