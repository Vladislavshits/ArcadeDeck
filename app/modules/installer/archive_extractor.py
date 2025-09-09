#!/usr/bin/env python3
import logging
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QThread
import time

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
        self.update_interval = 0.5  # Обновлять каждые 0.5 секунды
        self.extracted_files = []

    def _is_archive_file(self, file_path: Path) -> bool:
        """
        Определяет, является ли файл архивом по расширению.
        Только настоящие архивные форматы!
        """
        # ТОЛЬКО настоящие архивные форматы
        archive_extensions = [
            '.zip', '.rar', '.7z', '.tar',
            '.gz', '.bz2', '.xz', '.tgz',
            '.tbz2', '.txz', '.tar.gz', '.tar.bz2', '.tar.xz',
            '.cab', '.arj', '.lzh', '.lha'
        ]

        if file_path.suffix.lower() in archive_extensions:
            logger.info(f"📋 Определен архив по расширению: {file_path.suffix}")
            return True

        # Дополнительная проверка по сигнатурам ТОЛЬКО для архивных форматов
        try:
            with open(file_path, 'rb') as f:
                header = f.read(12)

            archive_signatures = {
                b'PK\x03\x04': 'ZIP',
                b'Rar!\x1A\x07\x00': 'RAR5',
                b'Rar!\x1A\x07\x01': 'RAR5',
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

        # Если это не архив - оставляем файл как есть
        logger.info(f"📋 Файл не является архивом: {file_path.suffix}")
        return False

    def _get_expected_filename(self) -> str:
        """Получает ожидаемое имя файла из данных игры"""
        try:
            # Пытаемся получить имя файла из torrent_url или magnet ссылки
            torrent_url = self.game_data.get("torrent_url", "")

            if torrent_url.startswith("magnet:"):
                # Парсим magnet ссылку для получения имени файла
                import re
                match = re.search(r"dn=([^&]+)", torrent_url)
                if match:
                    return match.group(1)

            elif torrent_url:
                # Для обычных torrent ссылок используем последнюю часть URL
                from urllib.parse import unquote, urlparse
                parsed_url = urlparse(torrent_url)
                filename = unquote(parsed_url.path.split("/")[-1])
                if filename:
                    return filename

            # Если не удалось получить из URL, используем ID игры как fallback
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

    def _format_size(self, bytes_size):
        """Форматирует размер в читаемый вид"""
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f}{unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f}ТБ"

    def _extract_archive(self, archive_path: Path):
        """Распаковывает архив с помощью libarchive"""
        try:
            import libarchive
            self.extracted_files = []  # Очищаем список перед распаковкой

            logger.info(f"📦 Распаковываю архив {archive_path.name}...")
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
                        progress_percent = int((extracted_size / total_size) * 100)
                        remaining_size = total_size - extracted_size

                        self.progress_updated.emit(
                            progress_percent,
                            f"📦 Распаковка: {progress_percent}% ({self._format_size(remaining_size)})"
                        )
                        self.last_update_time = current_time

            # Финальное обновление
            if not self._cancelled:
                archive_path.unlink()
                logger.info(f"✅ Архив удален: {archive_path.name}")
                self.progress_updated.emit(100, f"✅ Распаковано {extracted_files} файлов")

        except ImportError:
            raise Exception("libarchive не установлен. Установите: pip install libarchive-c")
        except Exception as e:
            raise Exception(f"Ошибка распаковки: {e}")

    def run(self):
        if self._cancelled:
            self.progress_updated.emit(0, "❌ Распаковка отменена")
            return

        downloaded_file = self._get_downloaded_file()
        if not downloaded_file:
            self.error_occurred.emit("Не найден скачанный файл")
            return

        logger.info(f"📄 Обрабатываю файл: {downloaded_file.name}")

        # Проверяем, является ли файл архивом
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
