#!/usr/bin/env python3
import subprocess
import re
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QThread
import libtorrent as lt
import requests
import time
import logging

logger = logging.getLogger('GameDownloader')


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
        self.session = None
        self.handle = None

    def _load_trackers_from_file(self) -> list:
        """Загружает список трекеров из текстового файла в папке installer."""
        trackers = []
        try:
            current_dir = Path(__file__).parent
            trackers_file = current_dir / "trackers.txt"

            if trackers_file.exists():
                with open(trackers_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            trackers.append(line)
                logger.info(f"✅ Загружено {len(trackers)} трекеров из {trackers_file}")
            else:
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

    def _setup_libtorrent_session(self):
        """Настраивает сессию libtorrent"""
        try:
            logger.info("Инициализация Libtorrent-сессии...")

            # Настройки Libtorrent
            settings = {
                'listen_interfaces': '0.0.0.0:6881-6999',  # Диапазон портов
                'download_rate_limit': 0,  # Без ограничения скорости скачивания
                'upload_rate_limit': 0,  # Без ограничения отдачи во время загрузки
                'active_downloads': 10,  # Больше активных загрузок
                'active_seeds': 5,  # Активные раздачи
                'active_limit': 200,  # Лимит активных торрентов
                'connections_limit': 1000,  # Максимальное количество соединений
                'connection_speed': 500,  # Скорость подключения (запросов в секунду)
                'enable_dht': True,
                'enable_lsd': True,
                'enable_upnp': True,
                'enable_natpmp': True,
                'max_peerlist_size': 5000,  # Большой список пиров
                'max_paused_peerlist_size': 5000,
                'max_metadata_size': 10000000,  # 10MB для метаданных
                'max_rejects': 100,  # Максимальное количество отклонений
                'recv_socket_buffer_size': 1048576,  # 1MB буфер приема
                'send_socket_buffer_size': 1048576,  # 1MB буфер отправки
                'file_pool_size': 500,  # Большой пул файлов
                'urlseed_wait_retry': 5,  # Быстрые ретраи
                'outgoing_port': 6881,  # Начальный порт
                'num_outgoing_ports': 199,  # Диапазон портов
                'send_buffer_low_watermark': 524288,  # 512KB
                'send_buffer_watermark': 2097152,  # 2MB
                'cache_size': 2048,  # 2GB кэша
                'cache_buffer_chunk_size': 16384,  # 16KB chunks
                'use_read_cache': True,
                'request_timeout': 10,
                'piece_timeout': 20,
                'inactivity_timeout': 20,
                'auto_manage_interval': 30,
            }

            self.session = lt.session(settings)

            # Добавляем DHT ноды для быстрого поиска пиров
            dht_nodes = [
                ("dht.libtorrent.org", 25401),
                ("router.bittorrent.com", 6881),
                ("router.utorrent.com", 6881),
                ("dht.transmissionbt.com", 6881),
                ("dht.aelitis.com", 6881)
            ]

            for node in dht_nodes:
                self.session.add_dht_node(node)

            return True

        except Exception as e:
            logger.error(f"Ошибка настройки Libtorrent-сессии: {e}")
            return False

    def _add_torrent_to_session(self, source: str) -> bool:
        """Добавляет торрент или magnet в сессию с трекерами из файла"""
        try:
            logger.info(f"Добавление торрента в сессию: {source[:100]}...")

            # Загружаем трекеры из файла
            additional_trackers = self._load_trackers_from_file()

            if source.startswith("magnet:"):
                logger.info("Обнаружена magnet-ссылка")

                # Парсим magnet ссылку
                params = lt.parse_magnet_uri(source)
                params.save_path = str(self.download_dir)
                params.storage_mode = lt.storage_mode_t.storage_mode_sparse

                # Добавляем дополнительные трекеры из файла
                for tracker in additional_trackers:
                    if tracker not in params.trackers:
                        params.trackers.append(tracker)
                        logger.info(f"Добавлен трекер: {tracker}")

                self.handle = self.session.add_torrent(params)
                logger.info("Magnet-ссылка добавлена в сессию")

            else:
                logger.info("Обнаружен torrent-файл")
                # Для torrent файлов
                info = lt.torrent_info(source)
                params = lt.add_torrent_params()
                params.ti = info
                params.save_path = str(self.download_dir)
                params.storage_mode = lt.storage_mode_t.storage_mode_sparse

                # Добавляем дополнительные трекеры
                for tracker in additional_trackers:
                    params.trackers.append(tracker)
                    logger.info(f"Добавлен трекер: {tracker}")

                self.handle = self.session.add_torrent(params)
                logger.info("Torrent файл добавлен в сессию")

            if self.handle:
                logger.info(f"✅ Торрент успешно добавлен")
                return True
            else:
                logger.error("❌ Не удалось создать handle для торрента")
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка добавления торрента в сессию: {e}")
            import traceback
            logger.error(f"🔍 Подробности ошибки: {traceback.format_exc()}")
            return False

    def run(self):
        logger.info("=" * 60)
        logger.info("🎮 ЗАПУСК СИСТЕМЫ УСТАНОВКИ ИГРЫ")
        logger.info("=" * 60)
        logger.info(f"📁 Папка загрузки: {self.download_dir}")
        logger.info(f"🎯 Игра: {self.game_data.get('title', 'Unknown')}")

        # Проверка отмены перед началом
        if self._cancelled:
            self.progress_updated.emit(0, "❌ Загрузка отменена до начала.")
            return

        # Проверяем все источники
        torrent_url = self.game_data.get("torrent_url")
        download_url = self.game_data.get("download_url")

        logger.info(f"Проверяем источники: torrent_url={bool(torrent_url)}, download_url={bool(download_url)}")

        # Сначала торрент, потом прямая ссылка
        if torrent_url:
            logger.info("Используем торрент для скачивания")
            self._download_via_torrent(torrent_url)
        elif download_url:
            logger.info("Используем прямую ссылку для скачивания")
            self._download_via_http(download_url)
        else:
            error_msg = "Отсутствует ссылка для скачивания (torrent_url или download_url)."
            logger.error(f"❌ {error_msg}")
            self.error_occurred.emit(error_msg)
            return

        logger.info("[TEST] GameDownloader run() завершился")

    def _download_via_torrent(self, source: str):
        self.progress_updated.emit(0, "⏳ Получение метаданных торрента...")

        # 1. Настраиваем сессию libtorrent
        if not self._setup_libtorrent_session():
            error_msg = "Не удалось инициализировать Libtorrent сессию"
            logger.error(f"❌ {error_msg}")
            self.error_occurred.emit(error_msg)
            return

        # 2. Добавляем торрент в сессию
        if not self._add_torrent_to_session(source):
            error_msg = "Не удалось добавить торрент в сессию"
            logger.error(f"❌ {error_msg}")
            self.error_occurred.emit(error_msg)
            return

        # 3. Мониторим прогресс загрузки
        logger.info("Начинаем мониторинг прогресса загрузки...")

        try:
            start_time = time.time()
            last_update_time = time.time()
            speed_samples = []
            last_progress = 0
            last_log_time = time.time()
            max_speed = 0

            while not self._cancelled and self.handle and self.handle.status().state != lt.torrent_status.seeding:
                # Проверка отмены в главном цикле
                if self._cancelled:
                    break

                status = self.handle.status()
                current_time = time.time()

                # Рассчитываем прогресс
                if status.total_wanted > 0:
                    progress = int((status.total_done / status.total_wanted) * 100)
                else:
                    progress = 0

                # Обновляем статус каждые 0.2 секунды для максимальной плавности
                if current_time - last_update_time > 0.2:
                    # Рассчитываем текущую скорость
                    instant_speed = status.download_rate / 1024  # KB/s

                    # Обновляем максимальную скорость
                    if instant_speed > max_speed:
                        max_speed = instant_speed

                    # Сглаживание скорости (скользящее среднее)
                    speed_samples.append(instant_speed)
                    if len(speed_samples) > 8:  # Больше samples для стабильности
                        speed_samples.pop(0)
                    avg_speed = sum(speed_samples) / len(speed_samples) if speed_samples else 0

                    # Рассчитываем ETA
                    if avg_speed > 10 and status.total_wanted > status.total_done:  # Минимум 10 KB/s
                        remaining_bytes = status.total_wanted - status.total_done
                        eta_seconds = remaining_bytes / (avg_speed * 1024)
                        hours = int(eta_seconds // 3600)
                        minutes = int((eta_seconds % 3600) // 60)
                        seconds = int(eta_seconds % 60)
                    else:
                        eta_seconds = 0
                        hours = minutes = seconds = 0

                    # Форматируем данные
                    downloaded_mb = status.total_done / (1024 * 1024)
                    total_mb = status.total_wanted / (1024 * 1024) if status.total_wanted > 0 else 0

                    # Создаем текст статуса
                    status_text = self._format_status_text(
                        progress=progress,
                        downloaded_mb=downloaded_mb,
                        total_mb=total_mb,
                        speed_kbs=avg_speed,
                        upload_kbs=status.upload_rate / 1024,
                        peers=status.num_peers,
                        seeds=status.num_seeds,
                        eta_seconds=eta_seconds,
                        state=status.state,
                        max_speed=max_speed
                    )

                    # === ОТЛАДКА ===
                    logger.info(f"[DOWNLOADER] EMIT → {progress}% | {status_text[:120]}...")
                    print(f"[DOWNLOADER] EMIT → {progress}% | {status_text[:80]}...")  # для консоли

                    # Отправляем обновления в UI
                    self.progress_updated.emit(progress, status_text)

                    # Логируем информацию каждые 1.5 секунды или при изменении прогресса
                    if current_time - last_log_time > 1.5 or progress != last_progress:
                        detail_log = (
                            f"📊 Прогресс: {progress}% | "
                            f"Скачано: {downloaded_mb:.1f}/{total_mb:.1f} MB | "
                            f"Скорость: {avg_speed:.1f} KB/s | "
                            f"Макс: {max_speed:.1f} KB/s | "
                            f"Пиров: {status.num_peers} | "
                            f"Сидов: {status.num_seeds}"
                        )

                        if eta_seconds > 0:
                            detail_log += f" | ETA: {hours:02d}:{minutes:02d}:{seconds:02d}"

                        logger.info(detail_log)
                        last_log_time = current_time

                    last_update_time = current_time
                    last_progress = progress

                time.sleep(0.05)  # Минимальная задержка для максимальной отзывчивости

            # Проверка отмены перед завершением
            if self._cancelled:
                logger.info("Загрузка отменена пользователем")
                self.progress_updated.emit(0, "Вы отменили загрузку")
                return

            # Проверяем завершение загрузки
            if not self._cancelled and self.handle and self.handle.status().state == lt.torrent_status.seeding:
                total_time = time.time() - start_time
                avg_speed_mb = (status.total_wanted / (1024 * 1024)) / total_time if total_time > 0 else 0

                logger.info(f"✅ Загрузка завершена за {total_time:.1f} секунд!")
                logger.info(f"🚀 Средняя скорость: {avg_speed_mb:.2f} MB/s")
                logger.info(f"🏆 Максимальная скорость: {max_speed/1024:.2f} MB/s")

                # === ОТЛАДКА ===
                logger.info(f"[DOWNLOADER HTTP] EMIT → {progress}% | {status_text[:100]}...")
                print(f"[DOWNLOADER HTTP] EMIT → {progress}% | {status_text[:80]}...")

                self.progress_updated.emit(progress, status_text)

                self.progress_updated.emit(100, f"✅ Скачивание завершено! Макс. скорость: {max_speed/1024:.1f} MB/s")
                self.finished.emit()

        except Exception as e:
            if not self._cancelled:
                error_msg = f"Ошибка во время загрузки: {e}"
                logger.error(f"❌ {error_msg}")
                self.error_occurred.emit(error_msg)

    def _download_via_http(self, url: str):
        """Метод для скачивания по прямой HTTP/HTTPS ссылке"""
        try:
            logger.info(f"Начинаем HTTP скачивание: {url[:100]}...")

            # Создаем временное имя файла для скачивания
            import uuid
            temp_filename = f"temp_download_{uuid.uuid4().hex[:8]}.tmp"
            destination_path = self.download_dir / temp_filename

            logger.info(f"📁 Временный файл: {destination_path}")

            # Проверяем, есть ли уже скачанные файлы в директории
            existing_files = list(self.download_dir.glob("*.*"))
            if existing_files:
                logger.info(f"📋 В директории уже есть {len(existing_files)} файлов")

            # Заголовки для запроса
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            # Отправляем запрос
            session = requests.Session()
            response = session.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()

            # Получаем общий размер
            total_size = int(response.headers.get('content-length', 0))
            if total_size == 0:
                total_size = self.game_data.get('size_bytes', 0)

            logger.info(f"📏 Общий размер файла: {total_size} байт")

            # Открываем файл для записи
            with open(destination_path, 'wb') as f:
                downloaded = 0
                last_update_time = time.time()
                speed_samples = []

                for chunk in response.iter_content(chunk_size=8192):
                    if self._cancelled:
                        logger.info("❌ Скачивание отменено пользователем")
                        # Удаляем временный файл при отмене
                        if destination_path.exists():
                            destination_path.unlink()
                        return

                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Обновляем прогресс каждые 0.2 секунды
                        current_time = time.time()
                        if current_time - last_update_time > 0.2:
                            # Вычисляем скорость
                            instant_speed = len(chunk) / (current_time - last_update_time)
                            speed_kbs = instant_speed / 1024

                            speed_samples.append(speed_kbs)
                            if len(speed_samples) > 8:
                                speed_samples.pop(0)
                            avg_speed = sum(speed_samples) / len(speed_samples) if speed_samples else 0

                            # Процент завершения
                            progress = 0
                            if total_size > 0:
                                progress = int((downloaded / total_size) * 100)

                            # Форматируем статус
                            downloaded_mb = downloaded / (1024 * 1024)
                            total_mb = total_size / (1024 * 1024) if total_size > 0 else 0

                            status_text = f"🌐 Скачивание... {downloaded_mb:.1f} МБ"
                            if total_size > 0:
                                status_text += f" из {total_mb:.1f} МБ"

                            status_text += f" — ⚡ {avg_speed:.1f} KB/s"

                            # ETA
                            if avg_speed > 10 and total_size > downloaded:
                                remaining_bytes = total_size - downloaded
                                eta_seconds = remaining_bytes / (avg_speed * 1024)
                                if eta_seconds > 0:
                                    hours = int(eta_seconds // 3600)
                                    minutes = int((eta_seconds % 3600) // 60)
                                    seconds = int(eta_seconds % 60)
                                    if hours > 0:
                                        status_text += f" — ⏰ {hours:02d}:{minutes:02d}:{seconds:02d}"
                                    else:
                                        status_text += f" — ⏰ {minutes:02d}:{seconds:02d}"

                            self.progress_updated.emit(progress, status_text)
                            last_update_time = current_time

                # Проверяем завершение
                if not self._cancelled:
                    final_size = destination_path.stat().st_size

                    # Переименовываем временный файл в нормальное имя
                    if final_size > 0:
                        # Ищем правильное расширение из URL
                        if '.zip' in url.lower():
                            extension = 'zip'
                        elif '.7z' in url.lower():
                            extension = '7z'
                        elif '.rar' in url.lower():
                            extension = 'rar'
                        elif '.nds' in url.lower():
                            extension = 'nds'
                        else:
                            # По умолчанию - zip (из логи видно, что это zip архив)
                            extension = 'zip'

                        final_filename = f"downloaded_game.{extension}"
                        final_path = self.download_dir / final_filename

                        # Проверяем, не существует ли уже файл
                        if final_path.exists():
                            # Добавляем суффикс, если файл уже существует
                            timestamp = int(time.time())  # Используем глобальную time
                            final_filename = f"downloaded_game_{timestamp}.{extension}"
                            final_path = self.download_dir / final_filename

                        # Переименовываем
                        destination_path.rename(final_path)
                        logger.info(f"✅ Файл переименован: {temp_filename} → {final_filename}")

                        if total_size > 0 and final_size != total_size:
                            logger.warning(f"⚠️ Размер файла не совпадает: {final_size} != {total_size}")
                            # Но все равно считаем успешным, так как файл скачан
                    else:
                        logger.error("❌ Скачанный файл имеет нулевой размер")
                        destination_path.unlink()  # Удаляем пустой файл
                        self.error_occurred.emit("Скачанный файл имеет нулевой размер")
                        return

                    logger.info(f"✅ HTTP скачивание завершено!")
                    self.progress_updated.emit(100, "✅ Скачивание завершено!")
                    self.finished.emit()

        except requests.exceptions.RequestException as e:
            if not self._cancelled:
                # Удаляем временный файл при ошибке
                if 'destination_path' in locals() and destination_path.exists():
                    destination_path.unlink()

                error_msg = f"Ошибка HTTP скачивания: {e}"
                logger.error(f"❌ {error_msg}")
                self.error_occurred.emit(error_msg)
        except Exception as e:
            if not self._cancelled:
                # Удаляем временный файл при ошибке
                if 'destination_path' in locals() and destination_path.exists():
                    destination_path.unlink()

                error_msg = f"Непредвиденная ошибка при HTTP скачивании: {e}"
                logger.error(f"❌ {error_msg}")
                self.error_occurred.emit(error_msg)

    def _format_status_text(self, progress, downloaded_mb, total_mb, speed_kbs,
                        upload_kbs, peers, seeds, eta_seconds, state, max_speed):
        """Форматирует текст статуса для отображения"""

        state_names = {
            lt.torrent_status.downloading: "Скачивание",
            lt.torrent_status.seeding: "Раздача",
            lt.torrent_status.checking_files: "Проверка",
            lt.torrent_status.downloading_metadata: "Получение метаданных",
            lt.torrent_status.finished: "Завершено",
        }

        state_text = state_names.get(state, "Подключение")

        # Конвертируем в MB/s для лучшего отображения
        speed_mbs = speed_kbs / 1024
        max_speed_mbs = max_speed / 1024

        status_text = f"{state_text}... {downloaded_mb:.1f} МБ из {total_mb:.1f} МБ"
        status_text += f" — ⚡ {speed_mbs:.1f} MB/s"
        status_text += f" — 🏆 {max_speed_mbs:.1f} MB/s"

        if upload_kbs > 10:  # Только если отдача существенная
            status_text += f" — 📤 {upload_kbs/1024:.1f} MB/s"

        status_text += f" — 👥 {peers} пиров ({seeds} сидов)"

        if eta_seconds > 0 and speed_mbs > 0.1:  # Минимум 0.1 MB/s
            hours = int(eta_seconds // 3600)
            minutes = int((eta_seconds % 3600) // 60)
            seconds = int(eta_seconds % 60)

            if hours > 0:
                status_text += f" — ⏰ {hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                status_text += f" — ⏰ {minutes:02d}:{seconds:02d}"
        else:
            status_text += " — 🔍 Поиск пиров..."

        return status_text

    def get_torrent_info_from_magnet(self, magnet_url: str) -> dict:
        """Получает информацию о содержимом торрента из magnet ссылки"""
        try:
            if not magnet_url.startswith("magnet:"):
                return {"error": "Не magnet ссылка"}

            # Парсим magnet ссылку
            params = lt.parse_magnet_uri(magnet_url)

            # Создаем временную сессию для получения метаданных
            temp_session = lt.session()
            temp_handle = temp_session.add_torrent(params)

            logger.info("Получение метаданных из magnet ссылки...")

            # Ждем получения метаданных (максимум 30 секунд)
            timeout = time.time() + 30
            while not temp_handle.has_metadata() and time.time() < timeout:
                time.sleep(0.1)

            if temp_handle.has_metadata():
                info = temp_handle.get_torrent_info()
                result = {
                    "name": info.name(),
                    "total_size": info.total_size(),
                    "num_files": info.num_files(),
                    "files": []
                }

                # Получаем список файлов
                for i in range(info.num_files()):
                    file_entry = info.file_at(i)
                    result["files"].append({
                        "path": file_entry.path,
                        "size": file_entry.size
                    })

                temp_session.remove_torrent(temp_handle)
                logger.info(f"Получены метаданные: {result['name']}, {result['num_files']} файлов")
                return result
            else:
                temp_session.remove_torrent(temp_handle)
                return {"error": "Не удалось получить метаданные"}

        except Exception as e:
            logger.error(f"❌ Ошибка получения информации из magnet: {e}")
            return {"error": str(e)}

    def get_torrent_info(self, torrent_file: str) -> dict:
        """Получает метаданные из локального .torrent-файла"""
        try:
            torrent_path = Path(torrent_file)
            if not torrent_path.exists() or not torrent_path.is_file():
                return {"error": "Файл не существует или не является файлом"}

            # Загружаем torrent_info напрямую из файла
            info = lt.torrent_info(str(torrent_path))

            result = {
                "name": info.name(),
                "total_size": info.total_size(),
                "num_files": info.num_files(),
                "files": []
            }

            # Получаем список файлов
            for i in range(info.num_files()):
                file_entry = info.file_at(i)
                result["files"].append({
                    "path": file_entry.path,
                    "size": file_entry.size
                })

            logger.info(f"Получены метаданные из torrent-файла: {result['name']}, {result['num_files']} файлов")
            return result

        except Exception as e:
            logger.error(f"❌ Ошибка чтения .torrent файла: {e}")
            return {"error": str(e)}

    def wait_for_metadata(self, timeout=60):
        """Ждет metadata для magnet (без скачивания файлов)"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.torrent_handle.has_metadata():
                return self.torrent_handle.get_torrent_info()  # Возвращаем dict с name, etc.
            time.sleep(1)
        return None

    def get_downloaded_file_path(self) -> Path:
        """Возвращает путь к скачанному файлу"""
        try:
            if self.handle and self.handle.status().has_metadata:
                info = self.handle.get_torrent_info()
                if info.num_files() == 1:
                    file_name = info.name()
                    file_path = self.download_dir / file_name
                    if file_path.exists():
                        logger.info(f"Найден скачанный файл: {file_name}")
                        return file_path
                else:
                    folder_name = info.name()
                    folder_path = self.download_dir / folder_name
                    if folder_path.exists():
                        logger.info(f"📁 Найдена скачанная папка: {folder_name}")
                        return folder_path

            # Fallback: ищем самый новый файл в директории
            current_time = time.time()
            newest_file = None
            newest_time = 0

            for file_path in self.download_dir.iterdir():
                if file_path.is_file() and file_path.stat().st_size > 0:
                    file_mtime = file_path.stat().st_mtime
                    file_age = current_time - file_mtime

                    # Ищем самый новый файл созданный в течение скачивания
                    if file_age < 30:  # 30 секунд
                        if file_mtime > newest_time:
                            newest_time = file_mtime
                            newest_file = file_path
                            logger.info(f"Кандидат: {file_path.name} (возраст: {file_age:.1f} сек)")

            if newest_file:
                logger.info(f"Выбран самый новый файл: {newest_file.name}")
                return newest_file

        except Exception as e:
            logger.error(f"❌ Ошибка поиска скачанного файла: {e}")

        logger.warning("⚠️ Скачанный файл не найден")
        return None

    def _cleanup_resources(self):
        """Очистка временных файлов и ресурсов"""
        try:
            # Для GameDownloader - удаляем частично скачанные торренты
            if hasattr(self, 'session') and self.session and hasattr(self, 'handle') and self.handle:
                try:
                    self.session.remove_torrent(self.handle)
                    logger.info("🗑️ Торрент удален из сессии")
                except Exception as e:
                    logger.error(f"❌ Ошибка удаления торрента: {e}")

            # Для ArchiveExtractor - удаляем частично распакованные файлы
            if hasattr(self, 'extracted_files'):
                for file_path in self.extracted_files:
                    try:
                        if file_path.exists():
                            file_path.unlink()
                            logger.info(f"🗑️ Удален распакованный файл: {file_path.name}")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось удалить файл {file_path.name}: {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка очистки ресурсов: {e}")

    def cancel(self):
        """ОТМЕНА ЗАГРУЗКИ ИГРЫ"""
        logger.info("Запрос отмены загрузки игры...")
        self._cancelled = True

        if self.session and self.handle:
            try:
                self.session.remove_torrent(self.handle)
                logger.info("🗑️ Торрент удален из сессии")
            except Exception as e:
                logger.error(f"❌ Ошибка при отмене загрузки: {e}")

        self.quit()
