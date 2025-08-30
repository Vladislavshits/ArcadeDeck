#!/usr/bin/env python3
import logging
import subprocess
import re
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QThread

logger = logging.getLogger('GameDownloader')


def convert_units(size_str: str) -> str:
    """
    Преобразует размеры из формата aria2c (MiB, GiB) в привычные МБ, ГБ.
    """
    if size_str.endswith("MiB"):
        return f"{float(size_str[:-3]):.1f} МБ"
    elif size_str.endswith("GiB"):
        return f"{float(size_str[:-3]):.1f} ГБ"
    elif size_str.endswith("KiB"):
        return f"{float(size_str[:-3]):.1f} КБ"
    return size_str


class GameDownloader(QThread):
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, game_data: dict, download_dir: Path, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self.download_dir = download_dir
        self._process = None
        self._cancelled = False

    def _load_trackers_from_file(self) -> list:
        """Загружает список трекеров из текстового файла в папке installer."""
        trackers = []
        try:
            # Определяем путь к trackers.txt относительно текущего файла
            current_dir = Path(__file__).parent
            trackers_file = current_dir / "trackers.txt"
            
            if trackers_file.exists():
                with open(trackers_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):  # Пропускаем пустые строки и комментарии
                            trackers.append(line)
                logger.info(f"✅ Загружено {len(trackers)} трекеров из {trackers_file}")
            else:
                # Создаем файл с default-трекерами, если его нет
                default_trackers = [
                    "udp://tracker.opentrackr.org:1337/announce",
                    "udp://open.demonii.com:1337/announce", 
                    "udp://open.stealth.si:80/announce",
                    "udp://exodus.desync.com:6969/announce"
                ]
                with open(trackers_file, 'w', encoding='utf-8') as f:
                    f.write("# Default trackers list\n")
                    for tracker in default_trackers:
                        f.write(f"{tracker}\n")
                trackers = default_trackers
                logger.info(f"✅ Создан файл {trackers_file} с трекерами по умолчанию")
                
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки трекеров из файла: {e}")
        
        return trackers

    def _extract_trackers_from_magnet(self, magnet_url: str) -> list:
        """Извлекает трекеры из magnet-ссылки."""
        trackers = []
        try:
            from urllib.parse import parse_qs, urlparse
            parsed = urlparse(magnet_url)
            query_params = parse_qs(parsed.query)
            if 'tr' in query_params:
                for tracker in query_params['tr']:
                    if tracker:  # Проверяем, что трекер не пустой
                        trackers.append(tracker)
                logger.info(f"✅ Извлечено {len(trackers)} трекеров из magnet-ссылки")
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения трекеров из magnet-ссылки: {e}")
        
        return trackers

    def run(self):
        if self._cancelled:
            self.progress_updated.emit(0, "❌ Загрузка отменена до начала.")
            return

        source = self.game_data.get("torrent_url")
        if not source:
            self.error_occurred.emit("Отсутствует ссылка для скачивания (torrent_url).")
            return

        # Определяем путь к aria2c в виртуальном окружении
        # Виртуальное окружение находится в ArcadeDeck/app/venv/
        project_root = Path(__file__).parent.parent.parent.parent  # Поднимаемся до ArcadeDeck/
        venv_bin_dir = project_root / 'app' / 'venv' / 'bin'
        aria2c_path = venv_bin_dir / 'aria2c'
        
        # Если в venv нет aria2c, используем системный (как fallback)
        if not aria2c_path.exists():
            aria2c_path = "aria2c"  # Системная версия
            logger.warning("⚠️ aria2c не найден в venv, используется системная версия")
        else:
            logger.info(f"✅ Используется aria2c из venv: {aria2c_path}")

        # 1. Загружаем трекеры из файла
        file_trackers = self._load_trackers_from_file()
        
        # 2. Извлекаем трекеры из magnet-ссылки (если это magnet)
        magnet_trackers = []
        if source.startswith("magnet:"):
            magnet_trackers = self._extract_trackers_from_magnet(source)
        
        # 3. Объединяем все трекеры, удаляем дубликаты
        all_trackers = list(set(file_trackers + magnet_trackers))
        logger.info(f"📊 Всего трекеров для использования: {len(all_trackers)}")
        
        # 4. Формируем команду aria2c
        cmd = [
            str(aria2c_path),  # Используем путь к aria2c из venv
            f"--dir={self.download_dir}",
            "--enable-dht=true",
            "--enable-dht6=true",
            "--dht-listen-port=6881-6999",
            "--enable-peer-exchange=true",
            "--bt-enable-lpd=true",
            "--allow-overwrite=true",
            "--check-integrity=true",
            "--seed-time=0",
            "--summary-interval=1",
            "--bt-request-peer-speed-limit=50K",
            "--max-overall-upload-limit=1K",
            "--max-connection-per-server=16",
            "--split=16",
            "--min-split-size=1M",
            "--bt-max-peers=500",
            "--bt-tracker-connect-timeout=10",
            "--bt-tracker-timeout=10",
            "--bt-stop-timeout=3600",
            "--listen-port=6881-6999",
            "--user-agent=Transmission/2.94",
            "--peer-id-prefix=-TR2940-"
        ]

        # 5. Добавляем все трекеры в команду
        for tracker in all_trackers:
            cmd.append(f"--bt-tracker={tracker}")

        cmd.append(source)

        # Остальная часть метода run() остается без изменений
        try:
            logger.info(f"📥 Запускаю загрузку: {' '.join(cmd[:5])}...")  # Логируем только начало команды
            
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Регулярка для парсинга прогресса
            progress_re = re.compile(
                r"\[#.+?\s+([\d\.]+[KMG]iB)/([\d\.]+[KMG]iB)\((\d+)%\).*DL:([\d\.]+[KMG]iB).*ETA:([^\]]+)\]"
            )

            for line in iter(self._process.stdout.readline, ''):
                if self._cancelled:
                    break
                    
                line = line.strip()
                if not line:
                    continue

                match = progress_re.search(line)
                if match:
                    downloaded = convert_units(match.group(1))
                    total = convert_units(match.group(2))
                    percent = int(match.group(3))
                    speed = convert_units(match.group(4))
                    eta = match.group(5) or "Файл почти загружен!"

                    status = f"Скачивание... {downloaded} из {total} — {speed} — ETA: {eta}"
                    self.progress_updated.emit(percent, status)
                    logger.info(status)

            if self._cancelled:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                self.progress_updated.emit(0, "❌ Загрузка отменена.")
                logger.info("❌ Загрузка отменена пользователем.")
                return

            self._process.wait()
                
            if self._process.returncode == 0:
                logger.info("✅ Скачивание завершено.")
                self.progress_updated.emit(100, "✅ Скачивание завершено!")
                self.finished.emit()
            else:
                error_msg = f"aria2c завершился с кодом {self._process.returncode}"
                logger.error(f"❌ {error_msg}")
                self.error_occurred.emit(error_msg)

        except Exception as e:
            if not self._cancelled:
                error_msg = f"Ошибка при запуске aria2c: {e}"
                logger.error(f"❌ {error_msg}")
                self.error_occurred.emit(error_msg)

    def get_downloaded_file_path(self) -> Path:
        """Возвращает путь к скачанному файлу"""
        try:
            # Ищем файлы в директории загрузки
            for file_path in self.download_dir.iterdir():
                if file_path.is_file():
                    logger.info(f"📄 Найден скачанный файл: {file_path.name}")
                    return file_path
        except Exception as e:
            logger.error(f"❌ Ошибка поиска скачанного файла: {e}")
        return None

    def cancel(self):
        self._process = None
        self._cancelled = True
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
