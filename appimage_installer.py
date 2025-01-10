#!/usr/bin/env python3
import os
import sys
import json
import shutil
import magic
import logging
import subprocess
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel,
                           QVBoxLayout, QWidget, QFileDialog, QMessageBox,
                           QListWidget, QHBoxLayout, QDialog, QLineEdit)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

# Log ayarları
logging.basicConfig(
    filename='appimage_installer.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class EditAppDialog(QDialog):
    def __init__(self, app_name, app_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Uygulama Düzenle")
        self.setGeometry(200, 200, 400, 100)
        
        layout = QVBoxLayout()
        
        # İsim düzenleme
        name_layout = QHBoxLayout()
        name_label = QLabel("Uygulama Adı:")
        self.name_edit = QLineEdit(app_name)
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)
        
        # Butonlar
        button_layout = QHBoxLayout()
        save_button = QPushButton("Kaydet")
        save_button.clicked.connect(self.accept)
        cancel_button = QPushButton("İptal")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        self.app_path = app_path
    
    def get_new_name(self):
        return self.name_edit.text()

class AppImageInstaller(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AppImage Yükleyici")
        self.setGeometry(100, 100, 600, 400)
        self.setWindowIcon(QIcon('app_icon.png'))
        
        # Yüklü uygulamalar listesi
        self.installed_apps = {}
        self.load_installed_apps()
        
        # Ana widget ve layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Başlık etiketi
        title_label = QLabel("AppImage Yükleyici")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Butonlar için yatay düzen
        button_layout = QHBoxLayout()
        
        # Dosya seçme butonu
        self.select_button = QPushButton("AppImage Dosyası Seç")
        self.select_button.clicked.connect(self.select_file)
        button_layout.addWidget(self.select_button)
        
        # Düzenle butonu
        self.edit_button = QPushButton("Seçili Uygulamayı Düzenle")
        self.edit_button.clicked.connect(self.edit_selected_app)
        self.edit_button.setEnabled(False)
        button_layout.addWidget(self.edit_button)
        
        # Kaldır butonu
        self.remove_button = QPushButton("Seçili Uygulamayı Kaldır")
        self.remove_button.clicked.connect(self.remove_selected_app)
        self.remove_button.setEnabled(False)
        button_layout.addWidget(self.remove_button)
        
        layout.addLayout(button_layout)
        
        # Yüklü uygulamalar listesi
        self.app_list = QListWidget()
        self.app_list.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.app_list)
        self.update_app_list()
        
        # Durum etiketi
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

    def load_installed_apps(self):
        apps_file = os.path.expanduser("~/.local/share/appimages/installed_apps.json")
        if os.path.exists(apps_file):
            try:
                with open(apps_file, 'r') as f:
                    self.installed_apps = json.load(f)
            except Exception as e:
                logging.error(f"Yüklü uygulamalar yüklenirken hata: {str(e)}")
                self.installed_apps = {}

    def save_installed_apps(self):
        apps_file = os.path.expanduser("~/.local/share/appimages/installed_apps.json")
        apps_dir = os.path.dirname(apps_file)
        os.makedirs(apps_dir, exist_ok=True)
        try:
            with open(apps_file, 'w') as f:
                json.dump(self.installed_apps, f, indent=2)
        except Exception as e:
            logging.error(f"Yüklü uygulamalar kaydedilirken hata: {str(e)}")

    def update_app_list(self):
        self.app_list.clear()
        for app_name in sorted(self.installed_apps.keys()):
            self.app_list.addItem(app_name)

    def on_selection_changed(self):
        has_selection = bool(self.app_list.selectedItems())
        self.edit_button.setEnabled(has_selection)
        self.remove_button.setEnabled(has_selection)

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "AppImage Dosyası Seç",
            os.path.expanduser("~"),
            "AppImage Files (*.AppImage);;All Files (*)"
        )
        
        if file_path:
            self.install_appimage(file_path)

    def edit_selected_app(self):
        selected_items = self.app_list.selectedItems()
        if not selected_items:
            return
        
        app_name = selected_items[0].text()
        app_info = self.installed_apps.get(app_name)
        if not app_info:
            return
        
        dialog = EditAppDialog(app_name, app_info['path'], self)
        if dialog.exec_() == QDialog.Accepted:
            new_name = dialog.get_new_name()
            if new_name and new_name != app_name:
                # Masaüstü dosyasını güncelle
                desktop_path = os.path.expanduser(f"~/Desktop/{app_name}.desktop")
                new_desktop_path = os.path.expanduser(f"~/Desktop/{new_name}.desktop")
                
                # Uygulamalar menüsü dosyasını güncelle
                apps_dir = os.path.expanduser("~/.local/share/applications")
                old_desktop_file = os.path.join(apps_dir, f"{app_name}.desktop")
                new_desktop_file = os.path.join(apps_dir, f"{new_name}.desktop")
                
                try:
                    # Desktop dosyalarını güncelle
                    if os.path.exists(desktop_path):
                        with open(desktop_path, 'r') as f:
                            content = f.read()
                        content = content.replace(f"Name={app_name}", f"Name={new_name}")
                        with open(new_desktop_path, 'w') as f:
                            f.write(content)
                        os.remove(desktop_path)
                    
                    if os.path.exists(old_desktop_file):
                        with open(old_desktop_file, 'r') as f:
                            content = f.read()
                        content = content.replace(f"Name={app_name}", f"Name={new_name}")
                        with open(new_desktop_file, 'w') as f:
                            f.write(content)
                        os.remove(old_desktop_file)
                    
                    # Yüklü uygulamalar listesini güncelle
                    self.installed_apps[new_name] = self.installed_apps.pop(app_name)
                    self.save_installed_apps()
                    self.update_app_list()
                    logging.info(f"Uygulama adı değiştirildi: {app_name} -> {new_name}")
                    
                except Exception as e:
                    logging.error(f"Uygulama düzenlenirken hata: {str(e)}")
                    QMessageBox.critical(self, "Hata", f"Uygulama düzenlenirken bir hata oluştu:\n{str(e)}")

    def remove_selected_app(self):
        selected_items = self.app_list.selectedItems()
        if not selected_items:
            return
        
        app_name = selected_items[0].text()
        reply = QMessageBox.question(
            self,
            "Uygulama Kaldır",
            f"{app_name} uygulamasını kaldırmak istediğinizden emin misiniz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                app_info = self.installed_apps.get(app_name)
                if app_info:
                    # AppImage dosyasını kaldır
                    if os.path.exists(app_info['path']):
                        os.remove(app_info['path'])
                    
                    # Masaüstü kısayolunu kaldır
                    desktop_path = os.path.expanduser(f"~/Desktop/{app_name}.desktop")
                    if os.path.exists(desktop_path):
                        os.remove(desktop_path)
                    
                    # Uygulamalar menüsü girişini kaldır
                    apps_dir = os.path.expanduser("~/.local/share/applications")
                    desktop_file = os.path.join(apps_dir, f"{app_name}.desktop")
                    if os.path.exists(desktop_file):
                        os.remove(desktop_file)
                    
                    # Listeden kaldır
                    del self.installed_apps[app_name]
                    self.save_installed_apps()
                    self.update_app_list()
                    logging.info(f"Uygulama kaldırıldı: {app_name}")
                    
                    QMessageBox.information(
                        self,
                        "Başarılı",
                        f"{app_name} başarıyla kaldırıldı!"
                    )
                
            except Exception as e:
                logging.error(f"Uygulama kaldırılırken hata: {str(e)}")
                QMessageBox.critical(self, "Hata", f"Uygulama kaldırılırken bir hata oluştu:\n{str(e)}")

    def install_appimage(self, file_path):
        try:
            # Dosya türünü kontrol et
            file_type = magic.from_file(file_path)
            if "executable" not in file_type.lower():
                logging.warning(f"Geçersiz dosya türü: {file_type}")
                QMessageBox.warning(self, "Hata", "Seçilen dosya çalıştırılabilir bir dosya değil!")
                return

            # Dosya adını al
            file_name = os.path.basename(file_path)
            app_name = os.path.splitext(file_name)[0]

            # Applications klasörü oluştur
            apps_dir = os.path.expanduser("~/.local/share/applications")
            os.makedirs(apps_dir, exist_ok=True)

            # AppImages klasörü oluştur
            appimages_dir = os.path.expanduser("~/.local/share/appimages")
            os.makedirs(appimages_dir, exist_ok=True)

            # AppImage dosyasını kopyala
            target_path = os.path.join(appimages_dir, file_name)
            shutil.copy2(file_path, target_path)
            os.chmod(target_path, 0o755)

            # Desktop dosyası oluştur
            icon_path = os.path.abspath("app_icon.png")
            desktop_file_content = f"""[Desktop Entry]
Name={app_name}
Exec={target_path}
Icon={icon_path}
Type=Application
Categories=Utility;
Terminal=false
"""
            desktop_file_path = os.path.join(apps_dir, f"{app_name}.desktop")
            with open(desktop_file_path, "w") as f:
                f.write(desktop_file_content)
            os.chmod(desktop_file_path, 0o755)

            # Masaüstüne kısayol oluştur
            desktop_dir = os.path.expanduser("~/Desktop")
            desktop_shortcut = os.path.join(desktop_dir, f"{app_name}.desktop")
            shutil.copy2(desktop_file_path, desktop_shortcut)
            os.chmod(desktop_shortcut, 0o755)

            # Yüklü uygulamalar listesine ekle
            self.installed_apps[app_name] = {
                'path': target_path,
                'install_date': datetime.now().isoformat()
            }
            self.save_installed_apps()
            self.update_app_list()

            logging.info(f"Uygulama yüklendi: {app_name}")
            QMessageBox.information(
                self,
                "Başarılı",
                f"{app_name} başarıyla yüklendi!\nMasaüstünde ve uygulamalar menüsünde bulabilirsiniz."
            )
            self.status_label.setText("Yükleme başarılı!")

        except Exception as e:
            logging.error(f"Yükleme hatası: {str(e)}")
            QMessageBox.critical(self, "Hata", f"Yükleme sırasında bir hata oluştu:\n{str(e)}")
            self.status_label.setText("Yükleme başarısız!")

def main():
    app = QApplication(sys.argv)
    window = AppImageInstaller()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 