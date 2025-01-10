#!/usr/bin/env python3
import os
import sys
import json
import shutil
import magic
import logging
import subprocess
import requests
import asyncio
import aiohttp
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel,
                           QVBoxLayout, QWidget, QFileDialog, QMessageBox,
                           QListWidget, QHBoxLayout, QDialog, QLineEdit,
                           QProgressBar)
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap

# Log ayarları
logging.basicConfig(
    filename='appimage_installer.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class IconSearchWorker(QThread):
    icon_found = pyqtSignal(str, str, bytes)
    search_completed = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, search_term):
        super().__init__()
        self.search_term = search_term
        self.session = None

    async def check_github_rate_limit(self, session):
        try:
            async with session.get('https://api.github.com/rate_limit') as response:
                if response.status == 200:
                    data = await response.json()
                    return data['resources']['search']['remaining'] > 0
                return False
        except:
            return False

    async def fetch_icon(self, session, url, source, headers=None):
        try:
            logging.info(f"{source}'dan ikon indiriliyor: {url}")
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    content = await response.read()
                    content_type = response.headers.get('content-type', '')
                    logging.info(f"İkon başarıyla indirildi: {source} - {content_type}")
                    self.icon_found.emit(url, source, content)
                    return True
                else:
                    logging.warning(f"İkon indirme hatası - {source}: HTTP {response.status}")
        except Exception as e:
            logging.error(f"İkon indirme hatası ({source}): {str(e)}")
        return False

    async def fetch_duckduckgo(self, session):
        encoded_term = self.search_term.replace(' ', '+')
        url = "https://duckduckgo.com/i.js"
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://duckduckgo.com/',
            'Origin': 'https://duckduckgo.com',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }
        params = {
            'q': f"{encoded_term} icon",
            'o': 'json',
            'vqd': '3-0',
            't': 'D',
            'l': 'us-en',
            'f': ',,,,,',
            'ia': 'images'
        }
        try:
            logging.info(f"DuckDuckGo API'sine istek gönderiliyor: {url}")
            async with session.get(url, headers=headers, params=params) as response:
                logging.info(f"DuckDuckGo yanıt kodu: {response.status}")
                if response.status == 200:
                    try:
                        data = await response.json()
                        logging.info(f"DuckDuckGo yanıtı alındı")
                        if 'results' in data:
                            for result in data['results'][:20]:
                                if 'image' in result:
                                    await self.fetch_icon(session, result['image'], "DuckDuckGo")
                        else:
                            logging.warning("DuckDuckGo'dan ikon bulunamadı")
                    except Exception as e:
                        logging.error(f"DuckDuckGo JSON ayrıştırma hatası: {str(e)}")
                else:
                    logging.warning(f"DuckDuckGo API yanıt hatası: {response.status}")
        except Exception as e:
            logging.error(f"DuckDuckGo API hatası: {str(e)}")

    async def fetch_icon_finder_free(self, session):
        """IconFinder'ın ücretsiz API'si"""
        search_term = self.search_term.replace(' ', '%20')
        url = f"https://api.iconify.design/search?query={search_term}&limit=5"
        try:
            logging.info(f"Iconify API'sine istek gönderiliyor: {url}")
            async with session.get(url) as response:
                logging.info(f"Iconify yanıt kodu: {response.status}")
                if response.status == 200:
                    try:
                        data = await response.json()
                        if isinstance(data, list) and len(data) > 0:
                            for icon in data[:5]:
                                if isinstance(icon, dict) and 'prefix' in icon and 'name' in icon:
                                    icon_url = f"https://api.iconify.design/{icon['prefix']}/{icon['name']}.svg"
                                    await self.fetch_icon(session, icon_url, "Iconify")
                    except Exception as e:
                        logging.error(f"Iconify JSON ayrıştırma hatası: {str(e)}")
                else:
                    logging.warning(f"Iconify API yanıt hatası: {response.status}")
        except Exception as e:
            logging.error(f"Iconify API hatası: {str(e)}")

    async def fetch_flaticon(self, session):
        """Flaticon'un web sitesinden doğrudan arama"""
        search_term = self.search_term.replace(' ', '+')
        url = f"https://www.flaticon.com/free-icons/{search_term}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.flaticon.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1'
        }
        try:
            logging.info(f"Flaticon'a istek gönderiliyor: {url}")
            async with session.get(url, headers=headers) as response:
                logging.info(f"Flaticon yanıt kodu: {response.status}")
                if response.status == 200:
                    html = await response.text()
                    # İkon URL'lerini bul
                    import re
                    icon_urls = re.findall(r'https://cdn-icons-png.flaticon.com/[^"\']+\.png', html)
                    logging.info(f"Flaticon'dan bulunan ikon sayısı: {len(icon_urls)}")
                    # İlk 20 ikonu al
                    for icon_url in icon_urls[:20]:
                        await self.fetch_icon(session, icon_url, "Flaticon")
                else:
                    logging.warning(f"Flaticon yanıt hatası: {response.status}")
        except Exception as e:
            logging.error(f"Flaticon hatası: {str(e)}")

    async def fetch_simpleicons(self, session):
        search_term = self.search_term.lower().replace(" ", "")
        url = f"https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/{search_term}.svg"
        try:
            logging.info(f"SimpleIcons'a istek gönderiliyor: {url}")
            async with session.get(url) as response:
                logging.info(f"SimpleIcons yanıt kodu: {response.status}")
                if response.status == 200:
                    await self.fetch_icon(session, url, "SimpleIcons")
                else:
                    logging.warning("SimpleIcons'dan ikon bulunamadı")
        except Exception as e:
            logging.error(f"SimpleIcons hatası: {str(e)}")

    async def fetch_openmoji(self, session):
        url = f"https://openmoji.org/data/color/svg/{self.search_term.lower()}.svg"
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    await self.fetch_icon(session, url, "OpenMoji")
        except Exception as e:
            logging.error(f"OpenMoji API hatası: {str(e)}")

    async def fetch_wikimedia(self, session):
        url = "https://commons.wikimedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": f"{self.search_term} icon filetype:png|svg",
            "srnamespace": "6",
            "srlimit": "20"
        }
        try:
            logging.info(f"Wikimedia API'sine istek gönderiliyor: {url}")
            async with session.get(url, params=params) as response:
                logging.info(f"Wikimedia yanıt kodu: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    results = data.get('query', {}).get('search', [])
                    logging.info(f"Wikimedia sonuç sayısı: {len(results)}")
                    for item in results:
                        title = item['title'].replace(' ', '_')
                        image_url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{title}"
                        await self.fetch_icon(session, image_url, "Wikimedia")
                else:
                    logging.warning(f"Wikimedia API yanıt hatası: {response.status}")
        except Exception as e:
            logging.error(f"Wikimedia API hatası: {str(e)}")

    async def search_icons(self):
        async with aiohttp.ClientSession() as session:
            self.session = session
            tasks = []

            # Flaticon'dan ara (öncelikli)
            tasks.append(self.fetch_flaticon(session))

            # DuckDuckGo API
            tasks.append(self.fetch_duckduckgo(session))

            # GitHub API (rate limit kontrolü ile)
            if await self.check_github_rate_limit(session):
                tasks.append(self.fetch_github(session))

            # SimpleIcons API
            tasks.append(self.fetch_simpleicons(session))

            # Wikimedia Commons API
            tasks.append(self.fetch_wikimedia(session))

            await asyncio.gather(*tasks)

    async def fetch_github(self, session):
        url = f"https://api.github.com/search/repositories?q={self.search_term}&per_page=20"
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Mozilla/5.0'
        }
        try:
            logging.info(f"GitHub API'sine istek gönderiliyor: {url}")
            async with session.get(url, headers=headers) as response:
                logging.info(f"GitHub yanıt kodu: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    logging.info(f"GitHub sonuç sayısı: {len(data.get('items', []))}")
                    for repo in data.get('items', []):
                        if 'owner' in repo and 'avatar_url' in repo['owner']:
                            await self.fetch_icon(session, repo['owner']['avatar_url'], "GitHub")
                else:
                    logging.warning(f"GitHub API yanıt hatası: {response.status}")
        except Exception as e:
            logging.error(f"GitHub API hatası: {str(e)}")

    def run(self):
        try:
            asyncio.run(self.search_icons())
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self.search_completed.emit()

class EditAppDialog(QDialog):
    def __init__(self, app_name, app_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Uygulama Düzenle")
        self.setGeometry(200, 200, 500, 300)
        self.app_info = app_info
        
        layout = QVBoxLayout()
        
        # İsim düzenleme
        name_layout = QHBoxLayout()
        name_label = QLabel("Uygulama Adı:")
        self.name_edit = QLineEdit(app_name)
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)
        
        # Açıklama düzenleme
        comment_layout = QHBoxLayout()
        comment_label = QLabel("Açıklama:")
        self.comment_edit = QLineEdit(app_info.get('comment', ''))
        comment_layout.addWidget(comment_label)
        comment_layout.addWidget(self.comment_edit)
        layout.addLayout(comment_layout)
        
        # İkon arama
        icon_search_layout = QHBoxLayout()
        self.icon_search_edit = QLineEdit()
        self.icon_search_edit.setPlaceholderText("İkon aramak için yazın...")
        icon_search_button = QPushButton("İkon Ara")
        icon_search_button.clicked.connect(self.search_icon)
        icon_search_layout.addWidget(self.icon_search_edit)
        icon_search_layout.addWidget(icon_search_button)
        layout.addLayout(icon_search_layout)
        
        # İkon önizleme ve seçenekler
        icon_preview_layout = QHBoxLayout()
        
        # Sol taraf - mevcut ikon
        current_icon_layout = QVBoxLayout()
        current_icon_label = QLabel("Mevcut İkon:")
        self.icon_label = QLabel()
        if 'icon' in app_info and os.path.exists(app_info['icon']):
            pixmap = QPixmap(app_info['icon'])
            self.icon_label.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        current_icon_layout.addWidget(current_icon_label)
        current_icon_layout.addWidget(self.icon_label)
        icon_preview_layout.addLayout(current_icon_layout)
        
        # Sağ taraf - bulunan ikonlar
        found_icons_layout = QVBoxLayout()
        found_icons_label = QLabel("Bulunan İkonlar:")
        self.found_icons_list = QListWidget()
        self.found_icons_list.setIconSize(QSize(48, 48))
        self.found_icons_list.setViewMode(QListWidget.IconMode)
        self.found_icons_list.setSpacing(10)
        self.found_icons_list.itemClicked.connect(self.select_found_icon)
        found_icons_layout.addWidget(found_icons_label)
        found_icons_layout.addWidget(self.found_icons_list)
        icon_preview_layout.addLayout(found_icons_layout)
        
        layout.addLayout(icon_preview_layout)
        
        # Yerel dosyadan seçme butonu
        local_icon_button = QPushButton("Yerel Dosyadan İkon Seç")
        local_icon_button.clicked.connect(self.select_local_icon)
        layout.addWidget(local_icon_button)
        
        # İlerleme çubuğu ekle
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
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
        self.new_icon_path = None
        self.temp_icon_dir = os.path.expanduser("~/.cache/appimage_installer/icons")
        os.makedirs(self.temp_icon_dir, exist_ok=True)
    
    def search_icon(self):
        search_term = self.icon_search_edit.text().strip()
        if not search_term:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir arama terimi girin!")
            return
        
        self.found_icons_list.clear()
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Belirsiz ilerleme
        
        self.worker = IconSearchWorker(search_term)
        self.worker.icon_found.connect(self.add_icon_to_list)
        self.worker.search_completed.connect(self.search_completed)
        self.worker.error_occurred.connect(self.search_error)
        self.worker.start()
    
    def add_icon_to_list(self, url, source, content):
        try:
            logging.info(f"İkon listeye ekleniyor: {source} - {url}")
            # Geçici dosya oluştur
            file_ext = '.png' if 'png' in url.lower() else '.svg'
            temp_icon_path = os.path.join(self.temp_icon_dir, f"temp_icon_{len(self.found_icons_list.findItems('', Qt.MatchContains))}{file_ext}")
            
            with open(temp_icon_path, 'wb') as f:
                f.write(content)
            
            # SVG dosyasını PNG'ye çevir
            if file_ext == '.svg':
                try:
                    from cairosvg import svg2png
                    png_path = temp_icon_path.replace('.svg', '.png')
                    svg2png(url=temp_icon_path, write_to=png_path, output_width=128, output_height=128)
                    temp_icon_path = png_path
                    logging.info(f"SVG başarıyla PNG'ye dönüştürüldü: {png_path}")
                except Exception as e:
                    logging.error(f"SVG dönüştürme hatası: {str(e)}")
                    if os.path.exists(temp_icon_path):
                        os.remove(temp_icon_path)
                    return
            
            # Listeye ekle
            pixmap = QPixmap(temp_icon_path)
            if not pixmap.isNull():
                try:
                    from PyQt5.QtWidgets import QListWidgetItem
                    item = QListWidgetItem()
                    item.setIcon(QIcon(pixmap))
                    item.setData(Qt.UserRole, temp_icon_path)
                    item.setText(f"{source}")
                    self.found_icons_list.addItem(item)
                    logging.info(f"İkon başarıyla listeye eklendi: {source}")
                except Exception as e:
                    logging.error(f"Liste öğesi oluşturma hatası: {str(e)}")
            else:
                logging.error(f"Geçersiz ikon dosyası: {temp_icon_path}")
                if os.path.exists(temp_icon_path):
                    os.remove(temp_icon_path)
        except Exception as e:
            logging.error(f"İkon ekleme hatası: {str(e)}")
            if 'temp_icon_path' in locals() and os.path.exists(temp_icon_path):
                os.remove(temp_icon_path)
    
    def search_completed(self):
        self.progress_bar.setVisible(False)
        count = self.found_icons_list.count()
        logging.info(f"İkon arama tamamlandı. Bulunan ikon sayısı: {count}")
        if count == 0:
            QMessageBox.information(self, "Bilgi", "Hiç ikon bulunamadı. Farklı bir arama terimi deneyin.")
        else:
            QMessageBox.information(self, "Bilgi", f"{count} adet ikon bulundu.")
    
    def search_error(self, error_message):
        self.progress_bar.setVisible(False)
        QMessageBox.warning(self, "Hata", f"İkon arama sırasında bir hata oluştu:\n{error_message}")
    
    def select_found_icon(self, item):
        icon_path = item.data(Qt.UserRole)
        if icon_path and os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            self.icon_label.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.new_icon_path = icon_path
    
    def select_local_icon(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "İkon Seç",
            os.path.expanduser("~"),
            "Resim Dosyaları (*.png *.jpg *.jpeg *.svg);;Tüm Dosyalar (*)"
        )
        
        if file_path:
            try:
                pixmap = QPixmap(file_path)
                self.icon_label.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.new_icon_path = file_path
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"İkon yüklenirken bir hata oluştu:\n{str(e)}")
    
    def cleanup_temp_icons(self):
        try:
            if os.path.exists(self.temp_icon_dir):
                shutil.rmtree(self.temp_icon_dir)
        except Exception as e:
            logging.error(f"Geçici ikonları temizleme hatası: {str(e)}")
    
    def accept(self):
        self.cleanup_temp_icons()
        super().accept()
    
    def reject(self):
        self.cleanup_temp_icons()
        super().reject()
    
    def get_new_info(self):
        info = {
            'name': self.name_edit.text(),
            'comment': self.comment_edit.text()
        }
        if self.new_icon_path:
            info['new_icon_path'] = self.new_icon_path
        return info

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

    def get_icon_path(self, app_name):
        try:
            # İkon dizinini oluştur
            icon_dir = os.path.expanduser("~/.local/share/icons/hicolor/128x128/apps")
            os.makedirs(icon_dir, exist_ok=True)
            icon_path = os.path.join(icon_dir, f"{app_name}.png")

            # Önce yerel AppImage'dan ikon çıkarmayı dene
            app_path = self.installed_apps.get(app_name, {}).get('path')
            if app_path and os.path.exists(app_path):
                try:
                    # AppImage'dan ikon çıkarma
                    subprocess.run([app_path, "--appimage-extract", "*.png"], 
                                stdout=subprocess.DEVNULL, 
                                stderr=subprocess.DEVNULL,
                                timeout=10)
                    squashfs_root = "squashfs-root"
                    if os.path.exists(squashfs_root):
                        for root, _, files in os.walk(squashfs_root):
                            for file in files:
                                if file.endswith('.png'):
                                    png_path = os.path.join(root, file)
                                    shutil.copy2(png_path, icon_path)
                                    shutil.rmtree(squashfs_root)
                                    return icon_path
                        shutil.rmtree(squashfs_root)
                except:
                    pass

            # İkon indirmeyi dene (birden fazla API ile)
            apis = [
                f"https://api.duckduckgo.com/?q={app_name}+icon&format=json&pretty=1",
                f"https://iconfinder-api.com/v4/icons/search?query={app_name}&count=1"
            ]

            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)'
            }

            for api_url in apis:
                try:
                    response = requests.get(api_url, headers=headers, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        
                        # DuckDuckGo API
                        if 'Image' in data and data['Image']:
                            img_url = data['Image']
                        # Iconfinder API
                        elif 'icons' in data and data['icons']:
                            img_url = data['icons'][0]['raster_sizes'][-1]['formats'][0]['preview_url']
                        else:
                            continue

                        img_response = requests.get(img_url, headers=headers, timeout=5)
                        if img_response.status_code == 200:
                            with open(icon_path, 'wb') as f:
                                f.write(img_response.content)
                            return icon_path
                except:
                    continue

            # Varsayılan ikonu kullan
            default_icon = os.path.abspath("app_icon.png")
            shutil.copy2(default_icon, icon_path)
            return icon_path

        except Exception as e:
            logging.error(f"İkon indirme hatası: {str(e)}")
            return os.path.abspath("app_icon.png")

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
        
        dialog = EditAppDialog(app_name, app_info, self)
        if dialog.exec_() == QDialog.Accepted:
            new_info = dialog.get_new_info()
            if new_info['name']:
                try:
                    # İkon güncelleme
                    if 'new_icon_path' in new_info:
                        icon_dir = os.path.expanduser("~/.local/share/icons/hicolor/128x128/apps")
                        os.makedirs(icon_dir, exist_ok=True)
                        new_icon_path = os.path.join(icon_dir, f"{new_info['name']}.png")
                        
                        # Yeni ikonu kopyala ve boyutlandır
                        pixmap = QPixmap(new_info['new_icon_path'])
                        scaled_pixmap = pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        scaled_pixmap.save(new_icon_path, "PNG")
                        
                        # Eski ikonu sil
                        if 'icon' in app_info and os.path.exists(app_info['icon']):
                            os.remove(app_info['icon'])
                        
                        app_info['icon'] = new_icon_path
                    
                    # Masaüstü ve menü dosyalarını güncelle
                    self.update_desktop_files(app_name, new_info)
                    
                    # Yüklü uygulamalar listesini güncelle
                    if new_info['name'] != app_name:
                        app_info = self.installed_apps.pop(app_name)
                    app_info.update({
                        'comment': new_info['comment']
                    })
                    self.installed_apps[new_info['name']] = app_info
                    self.save_installed_apps()
                    self.update_app_list()
                    
                    logging.info(f"Uygulama güncellendi: {app_name} -> {new_info['name']}")
                    QMessageBox.information(self, "Başarılı", "Uygulama başarıyla güncellendi!")
                    
                except Exception as e:
                    logging.error(f"Uygulama düzenlenirken hata: {str(e)}")
                    QMessageBox.critical(self, "Hata", f"Uygulama düzenlenirken bir hata oluştu:\n{str(e)}")

    def update_desktop_files(self, old_name, new_info):
        # Masaüstü dosyasını güncelle
        desktop_path = os.path.expanduser(f"~/Desktop/{old_name}.desktop")
        new_desktop_path = os.path.expanduser(f"~/Desktop/{new_info['name']}.desktop")
        
        # Uygulamalar menüsü dosyasını güncelle
        apps_dir = os.path.expanduser("~/.local/share/applications")
        old_desktop_file = os.path.join(apps_dir, f"{old_name}.desktop")
        new_desktop_file = os.path.join(apps_dir, f"{new_info['name']}.desktop")
        
        for old_path, new_path in [(desktop_path, new_desktop_path), (old_desktop_file, new_desktop_file)]:
            if os.path.exists(old_path):
                with open(old_path, 'r') as f:
                    content = f.read()
                
                content = content.replace(f"Name={old_name}", f"Name={new_info['name']}")
                if new_info.get('comment'):
                    if "Comment=" in content:
                        content = content.replace(content[content.find("Comment="):content.find("\n", content.find("Comment="))],
                                               f"Comment={new_info['comment']}")
                    else:
                        content = content.replace("[Desktop Entry]", f"[Desktop Entry]\nComment={new_info['comment']}")
                
                with open(new_path, 'w') as f:
                    f.write(content)
                
                if old_path != new_path:
                    os.remove(old_path)

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
                    
                    # İkonu kaldır
                    if 'icon' in app_info and os.path.exists(app_info['icon']):
                        os.remove(app_info['icon'])
                    
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

            # Eğer aynı isimde uygulama varsa kullanıcıya sor
            if app_name in self.installed_apps:
                reply = QMessageBox.question(
                    self,
                    "Uygulama Zaten Var",
                    f"{app_name} zaten yüklü. Üzerine yazmak ister misiniz?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return

            # AppImages klasörü oluştur
            appimages_dir = os.path.expanduser("~/.local/share/appimages")
            os.makedirs(appimages_dir, exist_ok=True)

            # AppImage dosyasını kopyala
            target_path = os.path.join(appimages_dir, file_name)
            shutil.copy2(file_path, target_path)
            os.chmod(target_path, 0o755)

            # Sandbox uyarısı
            sandbox_reply = QMessageBox.question(
                self,
                "Sandbox Modu",
                "Uygulamayı sandbox modunda çalıştırmak ister misiniz?\n(Daha güvenli ama bazı uygulamalar çalışmayabilir)",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            sandbox_param = "" if sandbox_reply == QMessageBox.No else "--no-sandbox"

            # İkon yolu al
            icon_path = self.get_icon_path(app_name)

            # Desktop dosyası oluştur
            desktop_file_content = f"""[Desktop Entry]
Version=1.0
Name={app_name}
Comment=AppImage uygulaması
Exec={target_path} {sandbox_param}
Icon={icon_path}
Terminal=false
Type=Application
Categories=Utility;Application;
"""
            # Applications klasörü oluştur ve desktop dosyasını kaydet
            apps_dir = os.path.expanduser("~/.local/share/applications")
            os.makedirs(apps_dir, exist_ok=True)
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
                'icon': icon_path,
                'install_date': datetime.now().isoformat(),
                'comment': 'AppImage uygulaması'
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