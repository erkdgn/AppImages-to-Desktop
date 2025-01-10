# AppImage Yükleyici

Bu uygulama, Ubuntu 24.04 ve diğer Linux sistemlerinde AppImage uygulamalarını kolayca yüklemek için tasarlanmış basit bir grafik arayüz uygulamasıdır.

## Özellikler

- AppImage dosyalarını seçme ve yükleme
- Masaüstüne kısayol oluşturma
- Uygulamalar menüsüne otomatik ekleme
- Basit ve kullanıcı dostu arayüz

## Gereksinimler

- Python 3.x
- PyQt5
- python-magic

## Kurulum

1. Gerekli paketleri yükleyin:
```bash
pip install -r requirements.txt
```

2. Uygulamayı çalıştırın:
```bash
python3 appimage_installer.py
```

## Kullanım

1. "AppImage Dosyası Seç" butonuna tıklayın
2. Yüklemek istediğiniz AppImage dosyasını seçin
3. Uygulama otomatik olarak:
   - AppImage dosyasını ~/.local/share/appimages dizinine kopyalar
   - Masaüstüne kısayol oluşturur
   - Uygulamalar menüsüne ekler

## Lisans

Bu proje MIT lisansı altında lisanslanmıştır. 