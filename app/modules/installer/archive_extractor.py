#!/usr/bin/env python3
import logging
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QThread

logger = logging.getLogger('ArchiveExtractor')

class ArchiveExtractor(QThread):
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, game_data: dict, download_dir: Path, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self.download_dir = download_dir
        self._cancelled = False

    def _is_archive_file(self, file_path: Path) -> bool:
        """
        Определяет, является ли файл архивом по расширению и сигнатурам.
        Pure Python - без внешних зависимостей!
        """
        # 1. Проверка по расширению (быстро и просто)
        archive_extensions = [
            '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz',
            '.tgz', '.tbz2', '.txz', '.tar.gz', '.tar.bz2', '.tar.xz',
            '.cab', '.arj', '.lzh', '.lha', '.z', '.Z'
        ]
        
        if file_path.suffix.lower() in archive_extensions:
            logger.info(f"📋 Определено по расширению: {file_path.suffix}")
            return True
        
        # 2. Проверка по сигнатурам (магическим числам) - более надежно
        try:
            with open(file_path, 'rb') as f:
                header = f.read(12)  # Читаем первые 12 байт
            
            # Сигнатуры популярных архивных форматов
            archive_signatures = {
                b'PK\x03\x04': 'ZIP',
                b'Rar!\x1A\x07\x00': 'RAR5',
                b'Rar!\x1A\x07\x01': 'RAR5',
                b'7z\xBC\xAF\x27\x1C': '7ZIP',
                b'\x1F\x8B\x08': 'GZIP',
                b'BZh': 'BZIP2',
                b'\xFD7zXZ\x00': 'XZ',
                b'\x1F\x9D': 'TAR.Z (compress)',
                b'\x1F\xA0': 'TAR.Z (compress)',
                b'# archiver': 'ARJ',
                b'!<arch>': 'AR (Unix)',
                b'\x60\xEA': 'AR (Unix)',
                b'MSZIP': 'CAB (Microsoft)',
                b'MSCF': 'CAB (Microsoft)',
                b'-lh': 'LHA/LZH',
                b'-lz': 'LHA/LZH'
            }
            
            # Проверяем все сигнатуры
            for signature, format_name in archive_signatures.items():
                if header.startswith(signature):
                    logger.info(f"📋 Обнаружена сигнатура: {format_name}")
                    return True
            
            # 3. Специальная проверка для TAR архивов
            if len(header) >= 512:
                # TAR архивы имеют специфичную структуру в первых 512 байтах
                # ustar magic в позиции 257-262
                if header[257:262] == b'ustar' or header[257:263] == b'ustar ':
                    logger.info("📋 Обнаружена сигнатура TAR (ustar)")
                    return True
                
                # GNU tar magic
                if header[257:263] == b'ustar\x00':
                    logger.info("📋 Обнаружена сигнатура TAR (GNU)")
                    return True
            
            # 4. Проверка для старых RAR форматов
            if header.startswith(b'Rar!\x1A\x07'):
                logger.info("📋 Обнаружена сигнатура RAR (старая)")
                return True
            
            # 5. Если ничего не найдено, логируем для отладки
            logger.info(f"🔍 Сигнатура не распознана: {header[:8].hex(' ').upper()}")
            
        except Exception as e:
            logger.warning(f"⚠️ Не удалось прочитать сигнатуру файла: {e}")
            # В случае ошибки чтения, доверяем расширению
            return file_path.suffix.lower() in archive_extensions
        
        # 6. Дополнительная эвристика: если файл большой и нет известного расширения,
        # но есть непонятная сигнатура - считаем архивом для безопасности
        file_size = file_path.stat().st_size
        if file_size > 1024 * 1024:  # > 1MB
            logger.info(f"📦 Большой файл без известного формата, считаем архивом (размер: {file_size} bytes)")
            return True
        
        return False

    def _get_downloaded_file(self) -> Path:
        """Находит скачанный файл в директории"""
        try:
            files = list(self.download_dir.iterdir())
            if not files:
                logger.error("❌ Директория загрузки пуста")
                return None

            # Берем первый найденный файл (в установщике всегда только один файл)
            for file_path in files:
                if file_path.is_file() and not file_path.name.startswith('.'):
                    logger.info(f"🔍 Найден файл: {file_path.name} (размер: {file_path.stat().st_size} bytes)")
                    return file_path

            logger.error("❌ Не найден файл для обработки")
            return None

        except Exception as e:
            logger.error(f"❌ Ошибка поиска скачанного файла: {e}")
            return None

    def _extract_archive(self, archive_path: Path):
        """Распаковывает архив с помощью libarchive с отображением прогресса"""
        try:
            import libarchive

            logger.info(f"📦 Распаковываю архив {archive_path.name} с помощью libarchive...")
            self.progress_updated.emit(0, "📊 Подсчет файлов в архиве...")

            # Первый проход: подсчитываем общее количество файлов
            total_files = 0
            total_size = 0
            with libarchive.file_reader(str(archive_path)) as archive:
                for entry in archive:
                    if entry.isdir:
                        continue
                    total_files += 1
                    total_size += entry.size

            if total_files == 0:
                logger.warning("⚠️ Архив пуст или содержит только директории")
                self.progress_updated.emit(100, "✅ Архив пуст - нечего распаковывать")
                return

            logger.info(f"📊 В архиве {total_files} файлов, общий размер: {total_size} bytes")
            self.progress_updated.emit(0, f"📦 Начинаю распаковку {total_files} файлов...")

            # Второй проход: распаковываем файлы с прогрессом
            extracted_files = 0
            extracted_size = 0

            with libarchive.file_reader(str(archive_path)) as archive:
                for entry in archive:
                    if self._cancelled:
                        break

                    if entry.isdir:
                        # Создаем директорию
                        target_dir = self.download_dir / entry.pathname
                        target_dir.mkdir(parents=True, exist_ok=True)
                        continue

                    # Распаковываем файл
                    target_file = self.download_dir / entry.pathname
                    target_file.parent.mkdir(parents=True, exist_ok=True)

                    with open(target_file, 'wb') as f:
                        for block in entry.get_blocks():
                            if self._cancelled:
                                break
                            f.write(block)
                            extracted_size += len(block)

                            # Обновляем прогресс по размеру
                            if total_size > 0:
                                size_progress = int((extracted_size / total_size) * 100)
                                self.progress_updated.emit(
                                    size_progress,
                                    f"📦 Распаковка: {size_progress}% ({extracted_size}/{total_size} bytes)"
                                )

                    extracted_files += 1

                    # Обновляем прогресс по количеству файлов
                    files_progress = int((extracted_files / total_files) * 100)
                    self.progress_updated.emit(
                        files_progress,
                        f"📄 Файлов: {extracted_files}/{total_files} ({files_progress}%)"
                    )

            if not self._cancelled:
                # Удаляем архив после успешной распаковки
                archive_path.unlink()
                logger.info(f"✅ Архив удален: {archive_path.name}")
                self.progress_updated.emit(100, f"✅ Распаковано {extracted_files} файлов")

        except ImportError:
            raise Exception("libarchive не установлен. Установите: pip install libarchive-c")
        except Exception as e:
            raise Exception(f"Ошибка распаковки архива {archive_path.name}: {e}")

    def run(self):
        if self._cancelled:
            self.progress_updated.emit(0, "❌ Распаковка отменена до начала.")
            return

        # Ищем скачанный файл
        downloaded_file = self._get_downloaded_file()
        if not downloaded_file:
            self.error_occurred.emit("Не найден скачанный файл для обработки.")
            return

        logger.info(f"📄 Обрабатываю файл: {downloaded_file.name}")
        logger.info(f"📋 Формат файла: {downloaded_file.suffix}")
        logger.info(f"📏 Размер файла: {downloaded_file.stat().st_size} bytes")

        # Проверяем, является ли файл архивом
        is_archive = self._is_archive_file(downloaded_file)
        logger.info(f"🔍 Результат проверки архива: {is_archive}")

        if not is_archive:
            message = f"✅ Файл не является архивом, оставляем как есть: {downloaded_file.name}"
            logger.info(message)
            self.progress_updated.emit(100, message)
            self.finished.emit()
            return

        # Если это архив - распаковываем
        try:
            logger.info(f"📦 Начинаю распаковку: {downloaded_file.name}")
            self.progress_updated.emit(0, f"Подготовка к распаковке: {downloaded_file.name}")

            self._extract_archive(downloaded_file)

            if not self._cancelled:
                success_message = "✅ Распаковка завершена успешно!"
                logger.info(success_message)
                self.progress_updated.emit(100, success_message)
                self.finished.emit()

        except Exception as e:
            if not self._cancelled:
                error_msg = f"Ошибка при распаковке: {e}"
                logger.error(f"❌ {error_msg}")
                self.error_occurred.emit(error_msg)

    def cancel(self):
        self._cancelled = True
        logger.info("🚫 Запрос отмены распаковки")
