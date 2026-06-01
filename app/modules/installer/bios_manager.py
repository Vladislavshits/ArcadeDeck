# bios_manager.py
#!/usr/bin/env python3
import json
import logging
import shutil
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlparse
from PyQt6.QtCore import QThread, pyqtSignal
import requests

logger = logging.getLogger('BIOSManager')


class YandexDownloader:
    """Загрузчик для Яндекс.Диска"""

    @staticmethod
    def download_file(url: str, target_path: Path, progress_callback=None) -> bool:
        """Скачивает файл с Яндекс.Диска"""
        try:
            logger.info("🎯 Загрузка с Яндекс.Диска")

            # Извлекаем public key из URL
            if '/d/' in url:
                public_key = url.split('/d/')[1].split('/')[0].split('?')[0]
            else:
                public_key = url.split('/')[-1]

            # Получаем прямую ссылку через Яндекс API
            api_url = f"https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key=https://disk.yandex.ru/d/{public_key}"

            response = requests.get(api_url)
            if response.status_code != 200:
                logger.error("❌ Не удалось получить ссылку Яндекс.Диска")
                return False

            data = response.json()
            download_url = data.get('href')
            if not download_url:
                logger.error("❌ Не найдена ссылка для скачивания")
                return False

            # Скачиваем файл
            return YandexDownloader._download_direct(download_url, target_path, progress_callback)

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки с Яндекс.Диска: {e}")
            return False

    @staticmethod
    def _download_direct(url: str, target_path: Path, progress_callback=None) -> bool:
        """Прямая загрузка файла"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                'Accept': '*/*'
            }

            response = requests.get(url, stream=True, headers=headers, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0

            with open(target_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        if progress_callback and total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            mb_downloaded = downloaded_size / (1024 * 1024)
                            progress_callback(progress, f"📥 Загрузка файлов: {mb_downloaded:.1f}MB")

            logger.info(f"✅ Загрузка успешна: {target_path.name}")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки: {e}")
            return False


class BIOSDownloadThread(QThread):
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, bios_info: dict, target_dir: Path, platform: str):
        super().__init__()
        self.bios_info = bios_info
        self.target_dir = target_dir
        self.platform = platform
        self._cancelled = False

    def run(self):
        try:
            download_url = self.bios_info.get('bios_url')
            if not download_url:
                self.error_occurred.emit("URL загрузки не указан")
                return

            self.progress_updated.emit(0, "🔄 Подготовка к загрузке...")

            # Создаем временную директорию
            temp_dir = self.target_dir / "temp_download"
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Генерируем имя файла с расширением .zip
            filename = self._generate_filename(download_url)
            temp_file = temp_dir / filename

            # Скачиваем файл
            self.progress_updated.emit(10, "📥 Загрузка архива...")

            success = YandexDownloader.download_file(
                download_url,
                temp_file,
                progress_callback=self.progress_updated.emit
            )

            if not success:
                self.error_occurred.emit("Не удалось скачать архив")
                return

            if self._cancelled:
                self.progress_updated.emit(0, "❌ Загрузка отменена")
                return

            # ВСЕГДА ПЫТАЕМСЯ РАСПАКОВАТЬ КАК АРХИВ
            self.progress_updated.emit(90, "📦 Обработка файлов...")

            # Сначала пробуем определить тип архива по сигнатурам файлов
            if self._is_archive_by_signature(temp_file) or self._is_archive_by_extension(temp_file):
                logger.info(f"🔧 Распаковываю архив: {temp_file.name}")
                extracted_files = self._extract_archive(temp_file, self.target_dir)

                # Удаляем архив после успешной распаковки
                temp_file.unlink()
                logger.info(f"🗑️ Удалил архив: {temp_file.name}")

                # Логируем результат распаковки
                if extracted_files:
                    logger.info(f"✅ Распаковано {len(extracted_files)} файлов")
                    for file in extracted_files:
                        logger.info(f"📄 Распакован: {file.name}")
                else:
                    logger.warning("⚠️ Архив распакован, но файлы не найдены")
            else:
                # Если не удалось распаковать, пробуем скопировать как есть
                logger.warning(f"⚠️ Файл не является архивом, пробуем скопировать как есть: {temp_file.name}")
                try:
                    # Копируем файл с оригинальным именем
                    shutil.copy2(temp_file, self.target_dir / temp_file.name)
                    logger.info(f"📄 Файл скопирован как: {temp_file.name}")
                except Exception as copy_error:
                    logger.error(f"❌ Ошибка копирования файла: {copy_error}")

            # Очищаем временные файлы
            shutil.rmtree(temp_dir)

            # УСПЕШНО ЗАВЕРШАЕМСЯ БЕЗ ПРОВЕРКИ ФАЙЛОВ
            self.progress_updated.emit(100, "✅ Файлы готовы!")
            self.finished.emit(True, f"Файлы для {self.platform} успешно подготовлены")

        except Exception as e:
            error_msg = f"Ошибка загрузки: {e}"
            logger.error(f"❌ {error_msg}")
            self.error_occurred.emit(error_msg)

    def _generate_filename(self, url: str) -> str:
        """Генерирует имя файла на основе URL с принудительным добавлением .zip"""
        parsed = urlparse(url)
        filename = unquote(parsed.path.split('/')[-1])

        if not filename or filename == '/':
            import time
            filename = f"download_{int(time.time())}.zip"
        elif not any(filename.lower().endswith(ext) for ext in ['.zip', '.7z', '.rar', '.tar.gz', '.tar']):
            # Если нет расширения архива, добавляем .zip
            filename += ".zip"

        return filename

    def _is_archive_by_extension(self, file_path: Path) -> bool:
        """Проверяет, является ли файл архивом по расширению"""
        archive_extensions = ['.zip', '.7z', '.rar', '.tar.gz', '.tar']
        return file_path.suffix.lower() in archive_extensions

    def _is_archive_by_signature(self, file_path: Path) -> bool:
        """Проверяет, является ли файл архивом по сигнатурам файлов"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(8)  # Читаем первые 8 байт

            # ZIP signature
            if header.startswith(b'PK\x03\x04'):
                return True
            # 7z signature
            elif header.startswith(b'7z\xBC\xAF\x27\x1C'):
                return True
            # RAR signature
            elif header.startswith(b'Rar!\x1A\x07\x00'):
                return True
            # GZIP signature (for .tar.gz)
            elif header.startswith(b'\x1F\x8B'):
                return True
            # TAR signature
            elif header.startswith(b'ustar') or header[257:262] == b'ustar':
                return True

        except Exception as e:
            logger.warning(f"⚠️ Ошибка проверки сигнатуры файла: {e}")

        return False

    def _extract_archive(self, archive_path: Path, extract_to: Path) -> list:
        """Распаковывает архив и возвращает список распакованных файлов"""
        extracted_files = []

        try:
            # Сначала пробуем определить тип по сигнатуре
            if self._is_zip_by_signature(archive_path):
                logger.info(f"📦 Распаковываю ZIP архив (по сигнатуре): {archive_path.name}")
                return self._extract_zip(archive_path, extract_to)
            elif self._is_archive_by_extension(archive_path):
                file_ext = archive_path.suffix.lower()
                if file_ext == '.zip':
                    logger.info(f"📦 Распаковываю ZIP архив: {archive_path.name}")
                    return self._extract_zip(archive_path, extract_to)
                elif file_ext in ['.7z', '.rar']:
                    logger.info(f"📦 Распаковываю {file_ext} архив: {archive_path.name}")
                    return self._extract_with_libarchive(archive_path, extract_to)
                elif file_ext in ['.tar.gz', '.tar']:
                    logger.info(f"📦 Распаковываю TAR архив: {archive_path.name}")
                    return self._extract_tar(archive_path, extract_to)
            else:
                # Пробуем распаковать как ZIP (наиболее распространенный формат)
                logger.info(f"📦 Пробую распаковать как ZIP: {archive_path.name}")
                return self._extract_zip(archive_path, extract_to)

        except Exception as e:
            logger.error(f"❌ Ошибка распаковки архива: {e}")
            raise Exception(f"Ошибка распаковки: {e}")

        return extracted_files

    def _is_zip_by_signature(self, file_path: Path) -> bool:
        """Проверяет, является ли файл ZIP архивом по сигнатуре"""
        try:
            with open(file_path, 'rb') as f:
                return f.read(4) == b'PK\x03\x04'
        except:
            return False

    def _extract_zip(self, archive_path: Path, extract_to: Path) -> list:
        """Распаковывает ZIP архив"""
        extracted_files = []
        try:
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                # Получаем список файлов в архиве
                file_list = zip_ref.namelist()
                logger.info(f"📋 Файлы в ZIP архиве: {file_list}")

                # Распаковываем
                zip_ref.extractall(extract_to)

                # Собираем список распакованных файлов
                for file_name in file_list:
                    extracted_file = extract_to / file_name
                    if extracted_file.exists():
                        extracted_files.append(extracted_file)

            logger.info(f"✅ ZIP архив распакован: {archive_path.name}")
        except zipfile.BadZipFile:
            logger.error(f"❌ Файл не является ZIP архивом: {archive_path.name}")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка распаковки ZIP: {e}")
            raise

        return extracted_files

    def _extract_with_libarchive(self, archive_path: Path, extract_to: Path) -> list:
        """Распаковывает 7z/RAR архив с помощью libarchive"""
        extracted_files = []
        try:
            import libarchive
            with libarchive.file_reader(str(archive_path)) as archive:
                for entry in archive:
                    if not entry.isdir:
                        target_path = extract_to / entry.pathname
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(target_path, 'wb') as f:
                            for block in entry.get_blocks():
                                f.write(block)
                        extracted_files.append(target_path)
                        logger.info(f"📄 Распакован: {entry.pathname}")

            logger.info(f"✅ {archive_path.suffix.upper()} архив распакован: {archive_path.name}")
        except ImportError:
            logger.error("❌ Библиотека libarchive не установлена")
            raise Exception("Для распаковки 7z/RAR архивов требуется libarchive")
        except Exception as e:
            logger.error(f"❌ Ошибка распаковки {archive_path.suffix}: {e}")
            raise

        return extracted_files

    def _extract_tar(self, archive_path: Path, extract_to: Path) -> list:
        """Распаковывает TAR/TAR.GZ архив"""
        extracted_files = []
        try:
            import tarfile
            mode = 'r:gz' if archive_path.suffix == '.gz' else 'r'

            with tarfile.open(archive_path, mode) as tar_ref:
                # Получаем список файлов в архиве
                file_list = tar_ref.getnames()
                logger.info(f"📋 Файлы в TAR архиве: {file_list}")

                # Распаковываем
                tar_ref.extractall(extract_to)

                # Собираем список распакованных файлов
                for file_name in file_list:
                    extracted_file = extract_to / file_name
                    if extracted_file.exists():
                        extracted_files.append(extracted_file)

            logger.info(f"✅ TAR архив распакован: {archive_path.name}")
        except ImportError:
            logger.error("❌ Модуль tarfile не доступен")
            raise Exception("Для распаковки TAR архивов требуется модуль tarfile")
        except Exception as e:
            logger.error(f"❌ Ошибка распаковки TAR: {e}")
            raise

        return extracted_files

    def cancel(self):
        """🆕 ОТМЕНА ЗАГРУЗКИ BIOS"""
        self._cancelled = True
        logger.info("🛑 Отмена загрузки BIOS...")


class BIOSManager:
    """
    Класс для управления файлами BIOS.
    """
    def __init__(self, project_root: Path):
        super().__init__()
        self.project_root = project_root
        self._cancelled = False
        self.download_thread = None
        self.download_success = False
        logger.info("BIOSManager инициализирован (конфиги загружаются в install.py)")

    def _on_bios_download_finished(self, success: bool, message: str):
        """Вызывается при завершении загрузки BIOS"""
        self.download_success = success
        logger.info(f"Загрузка BIOS завершена: {success} — {message}")

        # Пробрасываем прогресс дальше (например, в InstallThread)
        if hasattr(self, 'progress_updated'):
            self.progress_updated.emit(100 if success else 0, message)

    def _on_bios_download_error(self, error_msg: str):
        """Вызывается при ошибке загрузки"""
        self.download_success = False
        logger.error(f"Ошибка загрузки BIOS: {error_msg}")
        if hasattr(self, 'progress_updated'):
            self.progress_updated.emit(0, f"Ошибка: {error_msg}")

    def _download_and_install_bios(self, bios_info: dict, target_dir: Path, platform: str, progress_callback=None) -> bool:
        """Загружает и устанавливает необходимые файлы"""
        if self._cancelled:
            return False

        download_url = bios_info.get('bios_url')
        if not download_url:
            return False

        logger.info(f"Загрузка файлов для {platform}")

        self.download_thread = BIOSDownloadThread(bios_info, target_dir, platform)

        # Пробрасываем прогресс из потока загрузки
        if progress_callback:
            self.download_thread.progress_updated.connect(progress_callback)

        # Подключаем наши обработчики
        self.download_thread.finished.connect(self._on_bios_download_finished)
        self.download_thread.error_occurred.connect(self._on_bios_download_error)

        self.download_thread.start()
        return True  # ← Теперь возвращаем True сразу — поток работает асинхронно

    def ensure_bios_for_platform(self, platform: str, bios_config: dict = None, progress_callback=None) -> bool:
        """
        Проверяет наличие необходимых файлов для указанной платформы. Принимает готовый конфиг из installer
        """
        if self._cancelled:
            return False

        logger.info(f"🔍 Проверка необходимых файлов для: {platform}")

        if not bios_config:
            logger.info(f"ℹ️ Для {platform} не требуются дополнительные файлы")
            return True

        # === ОСОБАЯ ЛОГИКА ДЛЯ PS3 ===
        if platform.upper() == 'PS3':
            return self._ensure_ps3_bios(bios_config, progress_callback)  # 🆕 ПЕРЕДАЕМ CALLBACK

        # Стандартная логика для других платформ
        return self._ensure_standard_bios(bios_config, platform, progress_callback)  # 🆕 ПЕРЕДАЕМ CALLBACK

    def _verify_ps3_system_files(self, ps3_config_dir: Path) -> bool:
        """
        Проверяет наличие и корректность системных файлов PS3
        """
        system_files_path = ps3_config_dir / "dev_flash"

        if not system_files_path.exists() or not system_files_path.is_dir():
            logger.info("📁 Системные файлы не обнаружены")
            return False

        # Проверяем объем системных файлов
        total_size = 0
        try:
            for file_path in system_files_path.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при анализе системных файлов: {e}")
            return False

        size_mb = total_size / (1024 * 1024)
        logger.info(f"📊 Объем системных файлов: {size_mb:.1f} MB")

        # Проверяем минимальный требуемый объем
        if size_mb < 180:
            logger.info(f"📁 Объем системных файлов недостаточен: {size_mb:.1f} MB")
            return False

        logger.info(f"Системные файлы готовы к работе")
        return True

    def _ensure_ps3_bios(self, bios_info: dict, progress_callback=None) -> bool:
        """
        Специальная логика для подготовки PS3
        """
        try:
            logger.info("🎮 Подготовка системных файлов PS3...")

            # Используем путь из настроек для PS3
            from core import get_users_subpath
            ps3_config_dir = Path(get_users_subpath("configs")) / "PS3" / "rpcs3"
            ps3_config_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"📁 Каталог для системных файлов: {ps3_config_dir}")

            # Проверяем, не подготовлены ли уже системные файлы
            if self._verify_ps3_system_files(ps3_config_dir):
                logger.info("Системные файлы уже подготовлены")
                if progress_callback:
                    progress_callback(100, "Системные файлы готовы")
                return True

            download_url = bios_info.get('bios_url')
            if not download_url:
                logger.info("ℹ️ Для PS3 не требуется дополнительная загрузка")
                return True

            # Загружаем и устанавливаем системные файлы
            return self._download_and_install_bios(bios_info, ps3_config_dir, "PS3", progress_callback)

        except Exception as e:
            logger.error(f"❌ Ошибка подготовки системных файлов: {e}")
            return False

    def _ensure_standard_bios(self, bios_info: dict, platform: str, progress_callback=None) -> bool:
        """
        Стандартная логика для BIOS других платформ
        """
        download_url = bios_info.get('bios_url')
        if not download_url:
            logger.info(f"ℹ️ Для {platform} не требуется дополнительная загрузка")
            return True

        # Создаем директорию для файлов
        from core import get_users_subpath
        bios_dir = Path(get_users_subpath("bios")) / platform
        bios_dir.mkdir(parents=True, exist_ok=True)

        # Скачиваем файлы
        return self._download_and_install_bios(bios_info, bios_dir, platform, progress_callback)

    def _download_and_install_bios(self, bios_info: dict, target_dir: Path, platform: str, progress_callback=None) -> bool:
        """Загружает и устанавливает необходимые файлы"""
        if self._cancelled:
            return False

        download_url = bios_info.get('bios_url')
        if not download_url:
            return False
        logger.info(f"⬇️ Загрузка файлов для {platform}")

        # Создаем и запускаем поток загрузки
        self.download_thread = BIOSDownloadThread(bios_info, target_dir, platform)
        if progress_callback:
            self.download_thread.progress_updated.connect(progress_callback)

        # Обработчики завершения
        self.download_success = False

        self.download_thread.finished.connect(self._on_bios_download_finished)
        self.download_thread.error_occurred.connect(self._on_bios_download_error)

        self.download_thread.start()
        return True

    def cancel(self):
        """🆕 ОТМЕНА ВСЕХ ОПЕРАЦИЙ BIOS"""
        self._cancelled = True
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.cancel()
            self.download_thread.wait(1000)  # Даем время на graceful shutdown
        logger.info("🛑 BIOSManager: все операции отменены")
