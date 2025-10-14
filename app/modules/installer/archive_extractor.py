#!/usr/bin/env python3
import logging
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QThread
import time
import subprocess
import shutil

logger = logging.getLogger('ArchiveExtractor')

class ArchiveExtractor(QThread):
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    files_extracted = pyqtSignal(list)

    def __init__(self, game_data: dict, download_dir: Path, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self.download_dir = download_dir
        self._cancelled = False
        self.last_update_time = 0
        self.update_interval = 0.5
        self.extracted_files = []

        # Проверяем зависимости при инициализации
        self._ensure_dependencies()

    def _ensure_dependencies(self):
        """Проверяет наличие необходимых зависимостей"""
        try:
            import rarfile
            logger.info("✅ rarfile доступен")
        except ImportError:
            logger.warning("⚠️ rarfile не установлен. RAR архивы могут не работать")

    def _is_archive_file(self, file_path: Path) -> bool:
        """
        Определяет, является ли файл архивом по расширению.
        """
        # Существующие расширения архивов
        archive_extensions = [
            '.zip', '.rar', '.7z', '.tar',
            '.gz', '.bz2', '.xz', '.tgz',
            '.tbz2', '.txz', '.tar.gz', '.tar.bz2', '.tar.xz',
            '.cab', '.arj', '.lzh', '.lha'
        ]

        # Проверка на PKG (для PS3)
        if file_path.suffix.lower() == '.pkg':
            logger.info(f"📦 Обнаружен PKG файл: {file_path.name}")
            return False  # Не распаковывать PKG!

        if file_path.suffix.lower() in archive_extensions:
            logger.info(f"📋 Определен архив по расширению: {file_path.suffix}")
            return True

        # Проверка сигнатур
        try:
            with open(file_path, 'rb') as f:
                header = f.read(12)

            archive_signatures = {
                b'PK\x03\x04': 'ZIP',
                b'Rar!\x1A\x07\x00': 'RAR5',
                b'Rar!\x1A\x07\x01': 'RAR5',
                b'Rar!\x1A\x07': 'RAR',
                b'7z\xBC\xAF\x27\x1C': '7ZIP',
                b'\x1F\x8B\x08': 'GZIP',
                b'BZh': 'BZIP2',
                b'\xFD7zXZ\x00': 'XZ',
                b'# archiver': 'ARJ',
                b'!<arch>': 'AR (Unix)',
                b'\x60\xEA': 'AR (Unix)',
                b'MSZIP': 'CAB (Microsoft)',
                b'MSCF': 'CAB (Microsoft)',
                b'-lh': 'LHA/LZH',
                b'-lz': 'LHA/LZH'
            }

            for signature, format_name in archive_signatures.items():
                if header.startswith(signature):
                    logger.info(f"📋 Обнаружена сигнатура архива: {format_name}")
                    return True

            # Проверка для TAR архивов
            if len(header) >= 512:
                if header[257:262] == b'ustar' or header[257:263] == b'ustar ':
                    logger.info("📋 Обнаружена сигнатура TAR")
                    return True

                if header[257:263] == b'ustar\x00':
                    logger.info("📋 Обнаружена сигнатура TAR (GNU)")
                    return True

        except Exception as e:
            logger.warning(f"⚠️ Не удалось прочитать сигнатуру файла: {e}")

        logger.info(f"📋 Файл не является архивом: {file_path.suffix}")
        return False

    def _check_archive_integrity(self, archive_path: Path) -> bool:
        """Проверяет целостность архива"""
        try:
            import libarchive
            # Простая проверка - пытаемся прочитать entries
            with libarchive.file_reader(str(archive_path)) as archive:
                entry_count = 0
                for entry in archive:
                    entry_count += 1
                    if entry_count > 10:  # Проверяем только первые 10 файлов
                        break
            logger.info(f"✅ Архив прошел базовую проверку целостности")
            return True
        except Exception as e:
            logger.error(f"❌ Архив поврежден: {e}")
            return False

    def _extract_rar_with_unrar(self, archive_path: Path):
        """Распаковывает RAR архив с помощью unrar (системная утилита)"""
        try:
            # Проверяем наличие unrar
            unrar_path = shutil.which('unrar')
            if not unrar_path:
                unrar_path = shutil.which('unrar-free')
                if not unrar_path:
                    raise Exception("unrar не установлен в системе. Установите: sudo pacman -S unrar")

            logger.info(f"🔧 Использую unrar: {unrar_path}")

            # Подсчет файлов для прогресса
            result = subprocess.run([
                unrar_path, 'lb', str(archive_path)
            ], capture_output=True, text=True, check=True)

            file_list = result.stdout.strip().split('\n')
            total_files = len([f for f in file_list if f.strip()])

            if total_files == 0:
                logger.warning("⚠️ RAR архив пуст")
                return

            logger.info(f"📊 В RAR архиве {total_files} файлов")
            self.progress_updated.emit(0, f"📦 Распаковка RAR ({total_files} файлов)...")

            # Распаковка
            result = subprocess.run([
                unrar_path, 'x', '-y', str(archive_path), str(self.download_dir)
            ], capture_output=True, text=True, check=True)

            logger.info("✅ RAR распаковка через unrar завершена")

            # Собираем список распакованных файлов
            self.extracted_files = []
            for file_path in self.download_dir.rglob('*'):
                if file_path.is_file() and file_path != archive_path:
                    self.extracted_files.append(file_path)

        except subprocess.CalledProcessError as e:
            raise Exception(f"Ошибка unrar: {e.stderr}")
        except Exception as e:
            raise Exception(f"Ошибка распаковки RAR: {e}")

    def _extract_with_rarfile(self, archive_path: Path):
        """Распаковка RAR через rarfile (Python библиотека)"""
        try:
            import rarfile
            logger.info("🔄 Пробую распаковку через rarfile...")

            # Настраиваем путь к unrar если нужно
            unrar_path = shutil.which('unrar')
            if unrar_path:
                rarfile.UNRAR_TOOL = unrar_path
                logger.info(f"🔧 Установлен путь к unrar: {unrar_path}")

            with rarfile.RarFile(str(archive_path)) as rf:
                file_list = rf.namelist()
                total_files = len(file_list)

                logger.info(f"📊 В RAR архиве {total_files} файлов")
                self.progress_updated.emit(0, f"📦 Распаковка RAR ({total_files} файлов)...")

                # Распаковка
                rf.extractall(path=str(self.download_dir))

            # Собираем список распакованных файлов
            self.extracted_files = []
            for file_path in self.download_dir.rglob('*'):
                if file_path.is_file() and file_path != archive_path:
                    self.extracted_files.append(file_path)

            logger.info(f"✅ Rarfile распаковал {len(self.extracted_files)} файлов")
            return True

        except ImportError:
            logger.warning("⚠️ rarfile не установлен")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка rarfile: {e}")
            return False

    def _extract_with_libarchive(self, archive_path: Path):
        """Распаковка через libarchive"""
        try:
            import libarchive
            self.extracted_files = []

            logger.info(f"📦 Распаковываю архив {archive_path.name} через libarchive...")
            self.progress_updated.emit(0, "📊 Подсчет файлов в архиве...")

            # Подсчет файлов и общего размера
            total_files = 0
            total_size = 0
            with libarchive.file_reader(str(archive_path)) as archive:
                for entry in archive:
                    if not entry.isdir:
                        total_files += 1
                        total_size += entry.size

            if total_files == 0:
                logger.warning("⚠️ Архив пуст")
                self.progress_updated.emit(100, "✅ Архив пуст")
                return

            logger.info(f"📊 В архиве {total_files} файлов, общий размер: {self._format_size(total_size)}")
            self.progress_updated.emit(0, f"📦 Распаковка {total_files} файлов...")

            # Распаковка
            extracted_files = 0
            extracted_size = 0
            start_time = time.time()
            self.last_update_time = start_time

            with libarchive.file_reader(str(archive_path)) as archive:
                for entry in archive:
                    if self._cancelled:
                        break

                    if entry.isdir:
                        target_dir = self.download_dir / entry.pathname
                        target_dir.mkdir(parents=True, exist_ok=True)
                        continue

                    target_file = self.download_dir / entry.pathname
                    target_file.parent.mkdir(parents=True, exist_ok=True)

                    with open(target_file, 'wb') as f:
                        for block in entry.get_blocks():
                            if self._cancelled:
                                break
                            f.write(block)
                            extracted_size += len(block)

                    # Добавляем файл в список распакованных
                    self.extracted_files.append(target_file)
                    extracted_files += 1

                    # Обновляем прогресс с ограниченной частотой
                    current_time = time.time()
                    if current_time - self.last_update_time >= self.update_interval:
                        progress_percent = int((extracted_size / total_size) * 100) if total_size > 0 else 0
                        remaining_size = total_size - extracted_size

                        self.progress_updated.emit(
                            progress_percent,
                            f"📦 Распаковка: {progress_percent}% ({self._format_size(remaining_size)})"
                        )
                        self.last_update_time = current_time

            # Финальное обновление
            if not self._cancelled:
                logger.info(f"✅ Распаковано {extracted_files} файлов через libarchive")
                self.progress_updated.emit(100, f"✅ Распаковано {extracted_files} файлов")

        except Exception as e:
            raise Exception(f"Ошибка libarchive: {e}")

    def _is_ps3_pkg_file(self, file_path: Path) -> bool:
        """Определяет, является ли файл PS3 PKG"""
        if file_path.suffix.lower() == '.pkg':
            logger.info(f"📦 Обнаружен PS3 PKG файл: {file_path.name}")
            return True
        return False

    def _is_ps3_iso_file(self, file_path: Path) -> bool:
        """Определяет, является ли файл PS3 ISO"""
        if file_path.suffix.lower() == '.iso':
            # Дополнительная проверка для PS3 ISO
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(16)
                    # Проверяем сигнатуры PS3 ISO
                    if header.startswith(b'PS3') or b'PLAYSTATION' in header.upper():
                        logger.info(f"🎮 Обнаружен PS3 ISO файл: {file_path.name}")
                        return True
            except:
                pass
        return False

    def _is_ps3_folder_structure(self, file_path: Path) -> bool:
        """Определяет, является ли папка структурой PS3 игры"""
        if file_path.is_dir():
            # Проверяем наличие ключевых файлов PS3
            ps3_files = [
                file_path / "EBOOT.BIN",
                file_path / "USRDIR" / "EBOOT.BIN",
                file_path / "PS3_GAME" / "PARAM.SFO",
                file_path / "PARAM.SFO"
            ]

            for ps3_file in ps3_files:
                if ps3_file.exists():
                    logger.info(f"📁 Обнаружена папка PS3 игры: {file_path.name}")
                    return True
        return False

    def _get_ps3_game_type(self, file_path: Path) -> str:
        """Определяет тип PS3 игры"""
        if self._is_ps3_pkg_file(file_path):
            return 'pkg'
        elif self._is_ps3_iso_file(file_path):
            return 'iso'
        elif self._is_ps3_folder_structure(file_path):
            return 'folder'
        else:
            return 'unknown'

    def _should_extract_ps3_file(self, file_path: Path) -> bool:
        """
        Определяет, нужно ли распаковывать файл для PS3.
        PKG - не распаковываем, остальное - по ситуации.
        """
        ps3_type = self._get_ps3_game_type(file_path)

        if ps3_type == 'pkg':
            logger.info(f"🚫 PS3 PKG файл не требует распаковки: {file_path.name}")
            return False
        elif ps3_type == 'iso':
            logger.info(f"✅ PS3 ISO файл оставляем как есть: {file_path.name}")
            return False
        elif ps3_type == 'folder':
            logger.info(f"📁 Папка PS3 игры уже готова: {file_path.name}")
            return False
        else:
            # Для неизвестных типов проверяем, является ли файл архивом
            return self._is_archive_file(file_path)

    def _extract_archive(self, archive_path: Path):
        """Умная распаковка с несколькими fallback'ами"""
        # Сначала проверяем целостность архива
        if not self._check_archive_integrity(archive_path):
            logger.warning("⚠️ Архив не прошел проверку целостности")

        # Определяем приоритет методов в зависимости от типа архива
        archive_ext = archive_path.suffix.lower()

        if archive_ext == '.rar':
            # Для RAR архивов пробуем в таком порядке:
            methods = [
                self._extract_with_rarfile,    # 1. rarfile (Python)
                self._extract_rar_with_unrar,  # 2. unrar (системная утилита)
                self._extract_with_libarchive  # 3. libarchive (fallback)
            ]
        else:
            # Для других архивов:
            methods = [
                self._extract_with_libarchive,  # 1. libarchive (основной)
                self._extract_with_rarfile,     # 2. rarfile (для совместимости)
                self._extract_rar_with_unrar    # 3. unrar (fallback)
            ]

        last_error = None
        for method in methods:
            try:
                logger.info(f"🔄 Пробую метод: {method.__name__}")
                result = method(archive_path)
                if result is not False:  # Если метод не вернул явный False
                    logger.info(f"✅ Метод {method.__name__} успешен")
                    return
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ Метод {method.__name__} не сработал: {e}")
                continue

        raise Exception(f"Все методы распаковки не сработали. Последняя ошибка: {last_error}")

    def _format_size(self, bytes_size):
        """Форматирует размер в читаемый вид"""
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f}{unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f}ТБ"

    def _get_expected_filename(self) -> str:
        """Получает ожидаемое имя файла из данных игры"""
        try:
            torrent_url = self.game_data.get("torrent_url", "")

            if torrent_url.startswith("magnet:"):
                import re
                match = re.search(r"dn=([^&]+)", torrent_url)
                if match:
                    return match.group(1)

            elif torrent_url:
                from urllib.parse import unquote, urlparse
                parsed_url = urlparse(torrent_url)
                filename = unquote(parsed_url.path.split("/")[-1])
                if filename:
                    return filename

            return f"{self.game_data.get('id', 'game')}.zip"

        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить имя файла из торрента: {e}")
            return f"{self.game_data.get('id', 'game')}.zip"

    def _get_downloaded_file(self) -> Path:
        """Находит скачанный файл в директории по ожидаемому имени"""
        try:
            expected_filename = self._get_expected_filename()
            logger.info(f"🔍 Ожидаемый файл: {expected_filename}")

            files = list(self.download_dir.iterdir())
            if not files:
                logger.error("❌ Директория загрузки пуста")
                return None

            # Сначала ищем точное совпадение
            for file_path in files:
                if (file_path.is_file() and not file_path.name.startswith('.') and
                    file_path.name == expected_filename):
                    logger.info(f"✅ Найден целевой файл: {file_path.name}")
                    return file_path

            # Если точного совпадения нет, ищем по частичному совпадению
            for file_path in files:
                if (file_path.is_file() and not file_path.name.startswith('.') and
                    expected_filename.split('.')[0] in file_path.name):
                    logger.info(f"🔍 Найден похожий файл: {file_path.name}")
                    return file_path

            # Fallback: возвращаем первый подходящий файл
            for file_path in files:
                if file_path.is_file() and not file_path.name.startswith('.'):
                    logger.warning(f"⚠️ Точное совпадение не найдено, использую: {file_path.name}")
                    return file_path

            logger.error("❌ Не найден файл для обработки")
            return None

        except Exception as e:
            logger.error(f"❌ Ошибка поиска скачанного файла: {e}")
            return None

    def run(self):
        if self._cancelled:
            self.progress_updated.emit(0, "❌ Распаковка отменена")
            return

        downloaded_file = self._get_downloaded_file()
        if not downloaded_file:
            self.error_occurred.emit("Не найден скачанный файл")
            return

        logger.info(f"📄 Обрабатываю файл: {downloaded_file.name}")

        # ОСОБАЯ ЛОГИКА ДЛЯ PS3 ИГР
        if self.game_data.get('platform') == 'PS3':
            ps3_type = self._get_ps3_game_type(downloaded_file)
            logger.info(f"🎮 Тип PS3 игры: {ps3_type}")

            if ps3_type == 'pkg':
                message = f"📦 PS3 PKG файл готов к установке: {downloaded_file.name}"
                logger.info(message)
                self.progress_updated.emit(100, message)
                self.finished.emit()
                return
            elif ps3_type in ['iso', 'folder']:
                message = f"✅ PS3 {ps3_type.upper()} готов к запуску: {downloaded_file.name}"
                logger.info(message)
                self.progress_updated.emit(100, message)
                self.finished.emit()
                return

        # Стандартная логика для других случаев
        is_archive = self._is_archive_file(downloaded_file)

        if not is_archive:
            message = f"✅ Файл не является архивом, оставляем как есть: {downloaded_file.name}"
            logger.info(message)
            self.progress_updated.emit(100, message)
            self.finished.emit()
            return

        # Распаковываем архив
        try:
            logger.info(f"📦 Начинаю распаковку: {downloaded_file.name}")
            self.progress_updated.emit(0, f"Подготовка к распаковке: {downloaded_file.name}")
            self._extract_archive(downloaded_file)

            if not self._cancelled:
                logger.info("✅ Распаковка завершена")
                # Отправляем список распакованных файлов
                self.files_extracted.emit(self.extracted_files)
                self.progress_updated.emit(100, "✅ Распаковка завершена")
                self.finished.emit()

        except Exception as e:
            if not self._cancelled:
                error_msg = f"Ошибка при распаковке: {e}"
                logger.error(f"❌ {error_msg}")
                self.error_occurred.emit(error_msg)

    def cancel(self):
        self._cancelled = True
        logger.info("🚫 Запрос отмены распаковки")
