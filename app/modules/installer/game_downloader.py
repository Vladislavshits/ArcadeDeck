#!/usr/bin/env python3
import logging
import subprocess
import re
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

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


class GameDownloader(QObject):
    """
    Класс для управления загрузкой игр с использованием aria2c (через subprocess).
    """
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, game_data: dict, download_dir: Path, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self.download_dir = download_dir

    def run(self):
        """
        Запускает процесс скачивания игры через aria2c.
        Магнет-ссылка берется из game_data['torrent_url'].
        """
        source = self.game_data.get("torrent_url")
        if not source:
            self.error_occurred.emit("Отсутствует ссылка для скачивания (torrent_url).")
            return

        cmd = [
            "aria2c",
            f"--dir={self.download_dir}",
            "--enable-dht",
            "--enable-peer-exchange",
            "--allow-overwrite=true",
            "--check-integrity=true",
            "--seed-time=0",
            "--summary-interval=1",
            "--bt-tracker=udp://tracker.opentrackr.org:1337/announce,"
            "udp://open.demonii.com:1337/announce,"
            "udp://open.stealth.si:80/announce,"
            "udp://exodus.desync.com:6969/announce,"
            "udp://tracker.srv00.com:6969/announce,"
            "udp://tracker.ololosh.space:6969/announce,"
            "udp://isk.richardsw.club:6969/announce,"
            "udp://hificode.in:6969/announce,"
            "udp://glotorrents.pw:6969/announce,"
            "http://share.hkg-fansub.info:80/announce.php,"
            "udp://ttk2.nbaonlineservice.com:6969/announce,"
            "udp://tracker.zupix.online:6969/announce,"
            "udp://tracker.valete.tf:9999/announce,"
            "udp://tracker.tryhackx.org:6969/announce,"
            "udp://tracker.torrust-demo.com:6969/announce,"
            "udp://tracker.therarbg.to:6969/announce,"
            "udp://tracker.theoks.net:6969/announce,"
            "udp://tracker.skillindia.site:6969/announce,"
            "udp://tracker.plx.im:6969/announce,"
            "udp://tracker.opentrackr.org:1337,"
            "http://pubt.net:2710/announce,"
            "udp://tracker.internetwarriors.net:1337/announce,"
            "udp://ipv4.tracker.harry.lu:80/announce",
            source
        ]

        try:
            logger.info(f"📥 Запускаю загрузку: {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # Регулярка для парсинга строк прогресса: процент, скачано/всего, скорость, ETA
            progress_re = re.compile(
                r"\[#.+?\s+([\d\.]+[KMG]iB)/([\d\.]+[KMG]iB)\((\d+)%\).*DL:([\d\.]+[KMG]iB).*ETA:([^\]]+)\]"
            )

            for line in process.stdout:
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

            process.wait()
            if process.returncode == 0:
                logger.info("✅ Скачивание завершено.")
                self.progress_updated.emit(100, "✅ Скачивание завершено!")
                self.finished.emit()
            else:
                error_msg = f"aria2c завершился с кодом {process.returncode}"
                logger.error(f"❌ {error_msg}")
                self.error_occurred.emit(error_msg)

        except Exception as e:
            error_msg = f"Ошибка при запуске aria2c: {e}"
            logger.error(f"❌ {error_msg}")
            self.error_occurred.emit(error_msg)
