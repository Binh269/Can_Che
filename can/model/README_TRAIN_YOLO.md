# Train YOLO doc trong luong

## 1. Cau truc dataset

Dat anh va label theo dung format YOLO:

```text
can/model/datasets/trong_luong_yolo/
  images/train/
  images/val/
  labels/train/
  labels/val/
```

Moi anh can co file label cung ten, vi du:

```text
images/train/can_001.jpg
labels/train/can_001.txt
```

Moi dong label la:

```text
class_id x_center y_center width height
```

Tat ca toa do la ty le 0..1 theo format YOLO.

## 2. Class can gan nhan

```text
0  -> so 0
1  -> so 1
2  -> so 2
3  -> so 3
4  -> so 4
5  -> so 5
6  -> so 6
7  -> so 7
8  -> so 8
9  -> so 9
10 -> dot
```

Nen gan bbox tung ky tu tren hang "Trong Luong (kg)". Vi du anh hien `10.25` thi co 5 bbox: `1`, `0`, `dot`, `2`, `5`.

## 3. Tao thu muc dataset

```powershell
python can/train_yolo_trong_luong.py --init
```

## 4. Lay anh tu media/ban_ghi

Anh ban ghi dang luu trong `media/ban_ghi`. Copy anh moi nhat sang thu muc gan nhan:

```powershell
python can/chuan_bi_anh_train_yolo.py --limit 1000
```

Anh se nam trong:

```text
can/model/datasets/trong_luong_yolo/images/to_label/
```

Sau khi gan nhan xong, chuyen anh/label sang `images/train`, `labels/train`, `images/val`, `labels/val`.

## 5. Tu dong gan nhan YOLO

Khuyen dung cach synthetic truoc: script lay anh nen that trong `media/ban_ghi`, tu ve LED 7 doan len anh va tao label chinh xac theo toa do ve. Cach nay khong phu thuoc OCR cu.

```powershell
python can/tao_dataset_yolo_tu_dong.py --reset --train 2000 --val 400
```

Script pseudo-label anh that van co san de thu nghiem, nhung chi nen dung khi anh debug bbox dung:

```powershell
python can/tu_dong_gan_nhan_yolo.py --overwrite --debug-dir can/model/debug_auto_label
```

Neu anh bi copy nham vao `labels/train` hoac `labels/val`, script se chuyen sang thu muc backup:

```text
can/model/datasets/trong_luong_yolo/_anh_dat_nham_trong_labels/
```

Ket qua dung phai co cap file:

```text
images/train/abc.jpg
labels/train/abc.txt
```

## 6. Train

Neu co GPU NVIDIA:

```powershell
python can/train_yolo_trong_luong.py --device 0 --epochs 200 --imgsz 960 --batch -1
```

Neu chi co CPU:

```powershell
python can/train_yolo_trong_luong.py --device cpu --epochs 200 --imgsz 960 --batch 4
```

Sau khi train, script tu copy model tot nhat vao:

```text
can/model/weights/trong_luong_yolo_best.pt
```

Ung dung se uu tien file nay truoc `yolo11x.pt`.

## 7. Goi y de dat do chinh xac tot

- Moi gia tri can nen co nhieu anh o cac muc sang, goc nghieng, khoang cach khac nhau.
- Nen co it nhat vai tram anh, chia khoang 80% train va 20% val.
- Label chi hang trong luong can doc, khong label hang don gia/thanh tien.
- Neu camera co vi tri co dinh, dung anh dung tu camera that de train.
