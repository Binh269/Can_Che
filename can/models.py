import json
from django.db import models


class Can(models.Model):
    """Model luu thong tin cac can dien tu."""
    ma_can = models.CharField(max_length=50, primary_key=True, verbose_name='Ma can')
    ten_can = models.CharField(max_length=200, verbose_name='Ten can')
    vi_tri = models.CharField(max_length=200, verbose_name='Vi tri')
    hang = models.CharField(max_length=100, verbose_name='Hang san xuat')
    ngay_lap_dat = models.DateField(verbose_name='Ngay lap dat')
    khoi_luong_toi_da = models.FloatField(verbose_name='Khoi luong toi da (kg)')
    api = models.CharField(max_length=500, verbose_name='API endpoint')
    hoat_dong = models.BooleanField(default=True, verbose_name='Hoat dong')

    class Meta:
        verbose_name = 'Can'
        verbose_name_plural = 'Danh sach can'
        ordering = ['ma_can']

    def __str__(self):
        return f"{self.ma_can} - {self.ten_can}"


class Camera(models.Model):
    """Model luu thong tin camera cua moi can."""
    can = models.ForeignKey(
        Can,
        on_delete=models.CASCADE,
        related_name='cameras',
        verbose_name='Can'
    )
    ten_camera = models.CharField(max_length=200, verbose_name='Ten camera')
    # api: URL WebRTC cua Pi (ws:// hoac http://)
    api = models.CharField(max_length=500, verbose_name='API/Endpoint WebRTC')
    hoat_dong = models.BooleanField(default=True, verbose_name='Hoat dong')

    class Meta:
        verbose_name = 'Camera'
        verbose_name_plural = 'Danh sach camera'

    def __str__(self):
        return f"{self.ten_camera} ({self.can.ma_can})"


class BanGhiCan(models.Model):
    """Model luu ban ghi do luong tu moi can."""
    can = models.ForeignKey(
        Can,
        on_delete=models.CASCADE,
        related_name='ban_ghi',
        verbose_name='Can'
    )
    khoi_luong = models.FloatField(verbose_name='Khoi luong (kg)')
    # anh: duong dan tuong doi trong thu muc media/ban_ghi/
    anh = models.ImageField(
        upload_to='ban_ghi/',
        null=True,
        blank=True,
        verbose_name='Anh'
    )
    thoi_gian = models.DateTimeField(verbose_name='Thoi gian')
    # du_lieu_goc: toan bo JSON tu API can, luu duoi dang chuoi
    du_lieu_goc = models.TextField(verbose_name='Du lieu goc', default='{}')

    @property
    def du_lieu_goc_dict(self):
        """Tra ve du_lieu_goc dang dict Python."""
        try:
            return json.loads(self.du_lieu_goc)
        except Exception:
            return {}

    class Meta:
        verbose_name = 'Ban ghi can'
        verbose_name_plural = 'Ban ghi can'
        ordering = ['-thoi_gian']

    def __str__(self):
        return f"{self.can.ma_can} - {self.khoi_luong}kg - {self.thoi_gian}"
