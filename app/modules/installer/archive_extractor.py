#!/usr/bin/env python3
import logging
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QThread
import time
import subprocess
import shutil

logger = logging.getLogger('Модуль распаковки архивов')


class ArchiveExtractor(QThread):
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    files_extracted = pyqtSignal(list)

    def __init__(self, game_data: dict, download_dir: Path, parent=None):
        """
        download_dir теперь может быть:
         - Path к директории (обычный случай: папка, куда libtorrent пишет файлы)
         - Path к самому архивному файлу (если вызывающий передаёт файл напрямую)
        """
        super().__init__(parent)
        self.game_data = game_data or {}
        self.download_dir = Path(download_dir)
        self._cancelled = False
        self.last_update_time = 0
        self.update_interval = 0.5
        self.extracted_files = []

        # Проверяем зависимости при инициализации
        self._ensure_dependencies()

    def _ensure_dependencies(self):
        """Проверяет наличие необходимых зависимостей"""
        try:
            import rarfile  # noqa: F401
            logger.info("✅ rarfile доступен")
        except ImportError:
            logger.warning("⚠️ rarfile не установлен. RAR архивы могут не работать")

    def _is_archive_file(self, file_path: Path) -> bool:
        """
        Определяет, является ли файл архивом по расширению или сигнатуре.
        """
        if not file_path or not file_path.exists() or not file_path.is_file():
            return False

        # Существующие расширения архивов
        archive_extensions = {
            '.zip', '.rar', '.7z', '.tar',
            '.gz', '.bz2', '.xz', '.tgz',
            '.tbz2', '.txz', '.tar.gz', '.tar.bz2', '.tar.xz',
            '.cab', '.arj', '.lzh', '.lha'
        }

        # Исключаем PKG для PS3 — это контейнер, не архив
        if file_path.suffix.lower() == '.pkg':
            return False

        if file_path.suffix.lower() in archive_extensions:
            logger.debug(f"[ArchiveExtractor] Расширение {file_path.suffix} распознано как архив.")
            return True

        # Проверка сигнатур (безопасно: читаем небольшое количество байт)
        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)
            # Сопоставления сигнатур
            if header.startswith(b'PK\x03\x04'):
                return True
            if header.startswith(b'Rar!'):
                return True
            if header.startswith(b'7z\xBC\xAF\x27\x1C'):
                return True
            if header.startswith(b'\x1F\x8B\x08'):  # gzip
                return True
            if header.startswith(b'BZh'):
                return True
        except Exception as e:
            logger.debug(f"[ArchiveExtractor] Не удалось прочитать сигнатуру {file_path}: {e}")

        return False

    def _check_archive_integrity(self, archive_path: Path) -> bool:
        """Проверяет целостность архива (мягкая проверка)."""
        try:
            import libarchive
            # Простая проверка - пытаемся прочитать несколько entries
            with libarchive.file_reader(str(archive_path)) as archive:
                entry_count = 0
                for entry in archive:
                    entry_count += 1
                    if entry_count > 5:
                        break
            return True
        except Exception:
            # Не фатальная — вернём False, но дальше попробуем другие методы
            return False

    def _extract_rar_with_unrar(self, archive_path: Path):
        """Распаковывает RAR архив с помощью системного unrar."""
        try:
            unrar_path = shutil.which('unrar') or shutil.which('unrar-free')
            if not unrar_path:
                raise Exception("unrar не установлен в системе")

            # Сначала получим список файлов для прогресса
            result = subprocess.run([unrar_path, 'lb', str(archive_path)], capture_output=True, text=True, check=True)
            file_list = [ln for ln in result.stdout.splitlines() if ln.strip()]
            total_files = len(file_list)
            if total_files == 0:
                logger.warning("⚠️ RAR архив пуст")
                return False

            self.progress_updated.emit(0, f"📦 Распаковка RAR ({total_files} файлов)...")
            subprocess.run([unrar_path, 'x', '-y', str(archive_path), str(self.download_dir)], capture_output=True, text=True, check=True)

            # Собираем список распакованных файлов
            self.extracted_files = [p for p in self.download_dir.rglob('*') if p.is_file() and p != archive_path]
            return True
        except subprocess.CalledProcessError as e:
            raise Exception(f"unrar error: {e.stderr}")
        except Exception as e:
            logger.debug(f"[ArchiveExtractor] _extract_rar_with_unrar failed: {e}")
            return False

    def _extract_with_rarfile(self, archive_path: Path):
        """Распаковка через rarfile (python)."""
        try:
            import rarfile
            unrar_path = shutil.which('unrar')
            if unrar_path:
                rarfile.UNRAR_TOOL = unrar_path

            with rarfile.RarFile(str(archive_path)) as rf:
                members = rf.namelist()
                total_files = len(members)
                self.progress_updated.emit(0, f"📦 Распаковка RAR ({total_files} файлов)...")
                rf.extractall(path=str(self.download_dir))

            self.extracted_files = [p for p in self.download_dir.rglob('*') if p.is_file() and p != archive_path]
            return True
        except ImportError:
            logger.debug("[ArchiveExtractor] rarfile не установлен")
            return False
        except Exception as e:
            logger.debug(f"[ArchiveExtractor] rarfile extraction failed: {e}")
            return False

    def _extract_with_libarchive(self, archive_path: Path):
        """Распаковка через libarchive."""
        try:
            import libarchive
            self.extracted_files = []
            total_size = 0
            total_files = 0
            with libarchive.file_reader(str(archive_path)) as archive:
                for entry in archive:
                    if not entry.isdir:
                        total_files += 1
                        total_size += getattr(entry, 'size', 0)

            if total_files == 0:
                self.progress_updated.emit(100, "✅ Архив пуст")
                return True  # считаем это успешным

            self.progress_updated.emit(0, f"📦 Распаковка {total_files} файлов...")
            extracted_size = 0
            self.last_update_time = time.time()

            with libarchive.file_reader(str(archive_path)) as archive:
                for entry in archive:
                    # 🆕 ПРОВЕРКА ОТМЕНЫ ВО ВРЕМЯ РАСПАКОВКИ
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
                            # 🆕 ПРОВЕРКА ОТМЕНЫ ПРИ ЧТЕНИИ БЛОКОВ
                            if self._cancelled:
                                break
                            f.write(block)
                            extracted_size += len(block)

                    self.extracted_files.append(target_file)

                    # Периодическое обновление прогресса
                    current_time = time.time()
                    if current_time - self.last_update_time >= self.update_interval:
                        percent = int((extracted_size / total_size) * 100) if total_size > 0 else 0
                        self.progress_updated.emit(percent, f"📦 Распаковка: {percent}%")
                        self.last_update_time = current_time

            self.progress_updated.emit(100, "✅ Распаковка завершена")
            return True
        except Exception as e:
            logger.debug(f"[ArchiveExtractor] libarchive failed: {e}")
            return False

    def _is_ps3_pkg_file(self, file_path: Path) -> bool:
        if file_path.suffix.lower() == '.pkg':
            return True
        return False

    def _is_ps3_iso_file(self, file_path: Path) -> bool:
        if file_path.suffix.lower() == '.iso':
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(16)
                    if header.startswith(b'PS3') or b'PLAYSTATION' in header.upper():
                        return True
            except Exception:
                pass
        return False

    def _is_ps3_folder_structure(self, file_path: Path) -> bool:
        if file_path.is_dir():
            ps3_files = [
                file_path / "EBOOT.BIN",
                file_path / "USRDIR" / "EBOOT.BIN",
                file_path / "PS3_GAME" / "PARAM.SFO",
                file_path / "PARAM.SFO"
            ]
            for pf in ps3_files:
                if pf.exists():
                    return True
        return False

    def _get_ps3_game_type(self, file_path: Path) -> str:
        if self._is_ps3_pkg_file(file_path):
            return 'pkg'
        if self._is_ps3_iso_file(file_path):
            return 'iso'
        if self._is_ps3_folder_structure(file_path):
            return 'folder'
        return 'unknown'

    def _extract_archive(self, archive_path: Path):
        """Главная логика распаковки с несколькими fallback-методами."""
        # Не прерываем на целостности — просто логируем
        ok = self._check_archive_integrity(archive_path)
        if not ok:
            logger.warning("⚠️ Архив не прошёл базовую проверку целостности. Попробуем распаковать всё равно.")

        archive_ext = archive_path.suffix.lower()
        if archive_ext == '.rar':
            methods = [self._extract_with_rarfile, self._extract_rar_with_unrar, self._extract_with_libarchive]
        else:
            methods = [self._extract_with_libarchive, self._extract_with_rarfile, self._extract_rar_with_unrar]

        last_error = None
        for m in methods:
            # 🆕 ПРОВЕРКА ОТМЕНЫ ПЕРЕД КАЖДЫМ МЕТОДОМ
            if self._cancelled:
                logger.info("🛑 Распаковка отменена пользователем")
                return

            try:
                logger.debug(f"[ArchiveExtractor] Попытка метода: {m.__name__} для {archive_path}")
                res = m(archive_path)
                if res is not False:
                    logger.debug(f"[ArchiveExtractor] Метод {m.__name__} успешен")
                    return
            except Exception as e:
                last_error = e
                logger.debug(f"[ArchiveExtractor] Метод {m.__name__} выдал ошибку: {e}")
                continue

        raise Exception(f"Все методы распаковки не сработали. Последняя ошибка: {last_error}")

    def _get_expected_filename(self) -> str | None:
        """
        Возвращает ожидаемое имя файла из game_data, если оно задано.
        Если torrent_url / id не указаны — возвращает None (не ожидаем фиксированного имени).
        """
        try:
            torrent_url = self.game_data.get("torrent_url", "")
            if torrent_url and isinstance(torrent_url, str):
                if torrent_url.startswith("magnet:"):
                    import re
                    match = re.search(r"dn=([^&]+)", torrent_url)
                    if match:
                        return match.group(1)
                else:
                    from urllib.parse import unquote, urlparse
                    parsed = urlparse(torrent_url)
                    filename = unquote(parsed.path.split("/")[-1])
                    if filename:
                        return filename
            # Если нет torrent_url — не ждем конкретного имени
            return None
        except Exception:
            return None

    def _get_downloaded_file(self) -> Path | None:
        """
        Находит скачанный файл в директории:
        - Если download_dir указывает на файл — возвращаем его.
        - Если задан ожидаемый filename — пытаемся его найти.
        - Иначе ищем любой архивный файл; если нет — возвращаем самый большой файл.
        """
        try:
            # Если вызвали с файлом — используем его
            if self.download_dir.exists() and self.download_dir.is_file():
                logger.info(f"🔍 Получен файл напрямую: {self.download_dir.name}")
                return self.download_dir

            expected_filename = self._get_expected_filename()
            if expected_filename:
                logger.info(f"🔍 Ожидаемый файл: {expected_filename}")

            logger.info(f"📁 Поиск в директории: {self.download_dir}")

            all_files = [p for p in self.download_dir.rglob('*') if p.is_file() and not p.name.startswith('.')]
            if not all_files:
                logger.error("❌ Директория загрузки пуста")
                return None

            logger.info(f"📋 Найдено файлов для проверки: {len(all_files)}")
            for f in all_files:
                logger.debug(f"  - {f.relative_to(self.download_dir)}")

            # Если есть ожидаемое имя — ищем точное совпадение (рекурсивно)
            if expected_filename:
                for f in all_files:
                    if f.name == expected_filename:
                        logger.info(f"✅ Найден целевой файл (точное совпадение): {f}")
                        return f
                base = expected_filename.split('.')[0]
                for f in all_files:
                    if base in f.name:
                        logger.info(f"🔍 Найден похожий файл: {f}")
                        return f

            # Ищем любой архивный файл
            archive_files = [f for f in all_files if self._is_archive_file(f)]
            if archive_files:
                # Выбираем самый большой архив
                chosen = max(archive_files, key=lambda p: p.stat().st_size)
                logger.info(f"📦 Выбираем архив: {chosen.relative_to(self.download_dir)}")
                return chosen

            # Если архивов нет — возвращаем самый большой файл как последний fallback
            chosen = max(all_files, key=lambda p: p.stat().st_size)
            logger.info(f"⚠️ Архивы не найдены — возвращаем самый большой файл: {chosen.relative_to(self.download_dir)}")
            return chosen

        except Exception as e:
            logger.error(f"❌ Ошибка поиска скачанного файла: {e}", exc_info=True)
            return None

    def run(self):
        # 🆕 ПРОВЕРКА ОТМЕНЫ ПЕРЕД НАЧАЛОМ
        if self._cancelled:
            self.progress_updated.emit(0, "❌ Распаковка отменена")
            return

        logger.info(f"🔍 Запущен ArchiveExtractor. Путь: {self.download_dir}")

        # Получаем файл (или используем переданный файл)
        downloaded_file = self._get_downloaded_file()
        if not downloaded_file:
            self.error_occurred.emit("Не найден скачанный файл")
            return

        logger.info(f"📄 Обрабатываю: {downloaded_file}")

        # Специальная логика для PS3
        if self.game_data.get('platform') == 'PS3':
            ps3_type = self._get_ps3_game_type(downloaded_file)
            logger.info(f"🎮 PS3 тип: {ps3_type}")
            if ps3_type == 'pkg':
                self.progress_updated.emit(100, f"📦 PS3 PKG: {downloaded_file.name}")
                self.finished.emit()
                return
            if ps3_type in ('iso', 'folder'):
                self.progress_updated.emit(100, f"✅ PS3 {ps3_type.upper()}: {downloaded_file.name}")
                self.finished.emit()
                return

        # Если файл не архив — ничего не распаковываем
        if not self._is_archive_file(downloaded_file):
            self.progress_updated.emit(100, f"✅ Не архив: {downloaded_file.name}")
            self.finished.emit()
            return

        # Распаковываем найденный архив в ту же директорию, где он лежит (downloaded_file.parent)
        try:
            logger.info(f"📦 Начинаю распаковку: {downloaded_file}")
            self.progress_updated.emit(0, f"Подготовка к распаковке: {downloaded_file.name}")

            # ВАЖНО: целевая директория — родитель архива (чтобы распаковать "туда, где лежит архив")
            target_dir = downloaded_file.parent
            # временно сохраняем текущий download_dir, чтобы методы работали одинаково
            prev_download_dir = self.download_dir
            self.download_dir = target_dir

            self._extract_archive(downloaded_file)

            # Восстанавливаем
            self.download_dir = prev_download_dir

            # ПРОВЕРКА ОТМЕНЫ ПОСЛЕ РАСПАКОВКИ
            if not self._cancelled:
                logger.info("✅ Распаковка завершена")
                self.files_extracted.emit(self.extracted_files)
                self.progress_updated.emit(100, "Распаковка завершена")

                # 🗑️ Удаляем архивный файл после успешной распаковки
                try:
                    if downloaded_file.exists():
                        downloaded_file.unlink()
                        logger.info(f"🗑️ Архив удалён: {downloaded_file.name}")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось удалить архив {downloaded_file.name}: {e}")

                self.finished.emit()
            else:
                logger.info("Распаковка отменена пользователем")
                self.progress_updated.emit(0, "❌ Распаковка отменена")

        except Exception as e:
            if not self._cancelled:
                error_msg = f"Ошибка при распаковке: {e}"
                logger.error(error_msg, exc_info=True)
                self.error_occurred.emit(error_msg)

    def cancel(self):
        """ОТМЕНА С ОЧИСТКОЙ"""
        logger.info(f"Отмена {self.__class__.__name__}")
        self._cancelled = True

        # Останавливаем активные процессы
        if hasattr(self, '_process') and self._process:
            try:
                self._process.terminate()
                self._process.wait(1000)
            except:
                pass
