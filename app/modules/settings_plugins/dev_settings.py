import time
import platform
import logging
import os
import zipfile
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QDialog, QTextEdit, QScrollArea,
    QMessageBox, QFileDialog, QCheckBox
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer, QProcess
try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger(__name__)


class LogViewerDialog(QDialog):
    """Окно просмотра лог-файла (статическое, обновляется таймером)."""
    def __init__(self, log_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Просмотр логов")
        self.resize(800, 600)
        layout = QVBoxLayout(self)

        # Панель управления
        control_layout = QHBoxLayout()
        self.auto_scroll_checkbox = QCheckBox("Автопрокрутка")

        # Загружаем настройку из конфига
        from settings import app_settings
        auto_scroll_enabled = app_settings.get_log_auto_scroll()
        self.auto_scroll_checkbox.setChecked(auto_scroll_enabled)
        self.auto_scroll_checkbox.toggled.connect(self.toggle_auto_scroll)
        control_layout.addWidget(self.auto_scroll_checkbox)

        self.clear_button = QPushButton("Очистить логи в окне")
        self.clear_button.clicked.connect(self.clear_display)
        control_layout.addWidget(self.clear_button)

        control_layout.addStretch()
        layout.addLayout(control_layout)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)

        self.log_path = log_path
        self.auto_scroll = auto_scroll_enabled
        self.last_file_position = 0  # Позиция в файле для отслеживания новых записей
        self.display_cleared = False  # Флаг очистки отображения

        # Обновлять раз в секунду
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.reload)
        self.timer.start(1000)
        self.reload()

    def toggle_auto_scroll(self, enabled):
        """Включение/выключение автопрокрутки с сохранением в настройки"""
        self.auto_scroll = enabled
        from settings import app_settings
        app_settings.set_log_auto_scroll(enabled)

    def clear_display(self):
        """Очищает только отображение в окне, не трогая файл лога"""
        self.text.clear()
        self.display_cleared = True
        # При очистке сбрасываем позицию, чтобы читать только новые записи
        self.last_file_position = 0
        logger.info("Очищено отображение логов в просмотрщике")

    def reload(self):
        try:
            # Определяем размер файла
            file_size = os.path.getsize(self.log_path)

            # Если файл уменьшился (например, перезаписан), сбрасываем позицию
            if file_size < self.last_file_position:
                self.last_file_position = 0

            # Читаем только новые данные, если не была выполнена очистка отображения
            if not self.display_cleared and self.last_file_position > 0 and file_size > self.last_file_position:
                with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    f.seek(self.last_file_position)
                    new_data = f.read()
                    current_content = self.text.toPlainText()
                    # Добавляем только новые данные к существующему содержимому
                    data = current_content + new_data
            else:
                # Читаем весь файл (первый запуск или после очистки)
                with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    data = f.read()

            # Обновляем позицию для следующего чтения
            self.last_file_position = file_size
            self.display_cleared = False

        except Exception as e:
            data = f"Не удалось прочитать лог: {e}"

        # Сохраняем позицию скролла
        scrollbar = self.text.verticalScrollBar()
        old_position = scrollbar.value()
        was_at_bottom = (old_position == scrollbar.maximum())

        # Обновляем текст только если есть новые данные или первая загрузка
        if data.strip() or self.last_file_position == 0:
            self.text.setPlainText(data)

            # Восстанавливаем позицию скролла
            if self.auto_scroll and was_at_bottom:
                # Прокручиваем вниз только если пользователь был внизу
                scrollbar.setValue(scrollbar.maximum())
            else:
                # Иначе сохраняем позицию
                scrollbar.setValue(old_position)


class DevSettingsPage(QWidget):
    """Страница «Инструменты отладки»."""
    def __init__(self, parent=None, log_path: str = None):
        super().__init__(parent)
        from datetime import datetime
        self.launch_time = datetime.now()

        # Автоматически определяем путь к логу, если не указан
        if log_path is None:
            # Пробуем получить путь из родительского окна
            try:
                if parent and hasattr(parent.window(), 'log_file'):
                    log_path = parent.window().log_file
                else:
                    # Стандартный путь в домашней директории
                    log_path = os.path.join(os.path.expanduser("~"), "ArcadeDeck", "logs", "arcadedeck.log")
            except:
                # Фолбэк на стандартный путь
                log_path = os.path.join(os.path.expanduser("~"), "ArcadeDeck", "logs", "arcadedeck.log")

        self.log_path = str(log_path)

        # Создаем директорию логов, если не существует
        log_dir = os.path.dirname(self.log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("Инструменты разработчика")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # Путь к лог-файлу (информация)
        log_path_label = QLabel(f"Лог-файл: {self.log_path}")
        log_path_label.setStyleSheet("color: #888; font-size: 12px;")
        log_path_label.setWordWrap(True)
        layout.addWidget(log_path_label)

        # 1) Уровень логирования
        hl = QHBoxLayout()
        hl.addWidget(QLabel("Уровень логирования:"))
        self.combo = QComboBox()
        self.combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])

        # Правильно: получаем текстовое имя уровня из целочисленного кода
        level_int = logging.getLogger().getEffectiveLevel()
        level_name = logging.getLevelName(level_int)
        self.combo.setCurrentText(level_name)
        self.combo.currentTextChanged.connect(self.on_level_changed)
        hl.addWidget(self.combo)
        layout.addLayout(hl)

        # 2) Кнопки для работы с логами
        log_buttons_layout = QHBoxLayout()

        btn_view = QPushButton("Открыть логи")
        btn_view.clicked.connect(self.open_log_viewer)
        log_buttons_layout.addWidget(btn_view)

        btn_archive = QPushButton("Создать архив логов")
        btn_archive.clicked.connect(self.create_logs_archive)
        log_buttons_layout.addWidget(btn_archive)

        layout.addLayout(log_buttons_layout)

        # 3) Кнопка «Оборудование» и скрытое окно с данными
        self.hw_btn = QPushButton("Оборудование ▲")
        self.hw_btn.setCheckable(True)
        self.hw_btn.toggled.connect(self.toggle_hw_info)
        layout.addWidget(self.hw_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self.hw_container = QWidget()
        self.hw_container.hide()
        hw_layout = QVBoxLayout(self.hw_container)
        hw_layout.setContentsMargins(10, 5, 10, 5)

        # Информация о системе
        self.lbl_steam_model = QLabel()
        self.lbl_steamos = QLabel()
        self.lbl_free = QLabel()
        self.lbl_launch = QLabel()
        self.lbl_cpu = QLabel()
        self.lbl_mem = QLabel()
        for lbl in (self.lbl_steam_model, self.lbl_steamos, self.lbl_free,
                    self.lbl_launch, self.lbl_cpu, self.lbl_mem):
            hw_layout.addWidget(lbl)

        layout.addWidget(self.hw_container)

        # Таймер для обновления stats
        self.hw_timer = QTimer(self)
        self.hw_timer.timeout.connect(self.update_hw_info)
        self.hw_timer.start(1000)

        layout.addStretch(1)

    def on_level_changed(self, level: str):
        lvl = getattr(logging, level, logging.INFO)
        logging.getLogger().setLevel(lvl)
        logger.info(f"Log level set to {level}")

    def open_log_viewer(self):
        # Проверяем существование файла лога
        if not os.path.exists(self.log_path):
            # Создаем пустой файл
            open(self.log_path, 'a').close()
            logger.info(f"Создан лог-файл: {self.log_path}")

        dlg = LogViewerDialog(self.log_path, parent=self.window())
        dlg.exec()

    def create_logs_archive(self):
        """Создает архив со всеми логами для отладки"""
        try:
            # Определяем директорию логов
            logs_dir = os.path.dirname(self.log_path)
            if not os.path.exists(logs_dir):
                QMessageBox.warning(self, "Ошибка", "Директория логов не найдена")
                return

            # Предлагаем выбрать место сохранения
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"arcadedeck_logs_{timestamp}.zip"

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Сохранить архив логов",
                default_filename,
                "ZIP Archives (*.zip)"
            )

            if not file_path:
                return  # Пользователь отменил

            # Создаем архив
            with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Добавляем все файлы из директории логов
                for root, dirs, files in os.walk(logs_dir):
                    for file in files:
                        file_path_full = os.path.join(root, file)
                        # Исключаем временные файлы и архивы
                        if not file.endswith(('.tmp', '.zip')):
                            # Сохраняем относительный путь в архиве
                            arcname = os.path.relpath(file_path_full, logs_dir)
                            zipf.write(file_path_full, arcname)

                            logger.info(f"Добавлен в архив: {file}")

                # Добавляем системную информацию
                system_info = self._get_system_info()
                zipf.writestr("system_info.txt", system_info)

            # Показываем сообщение об успехе
            archive_size = os.path.getsize(file_path) / 1024  # Размер в KB
            QMessageBox.information(
                self,
                "Архив создан",
                f"Архив логов успешно создан!\n\n"
                f"Файл: {os.path.basename(file_path)}\n"
                f"Размер: {archive_size:.1f} KB\n"
                f"Путь: {file_path}"
            )

            logger.info(f"Создан архив логов: {file_path} ({archive_size:.1f} KB)")

        except Exception as e:
            logger.error(f"Ошибка создания архива логов: {e}")
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось создать архив логов:\n{str(e)}"
            )

    def _get_system_info(self):
        """Собирает системную информацию для включения в архив"""
        info_lines = []
        info_lines.append("=== ArcadeDeck System Information ===")
        info_lines.append(f"Время сбора: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        info_lines.append("")

        # Информация о системе
        info_lines.append("--- Система ---")
        info_lines.append(f"Платформа: {platform.platform()}")
        info_lines.append(f"Процессор: {platform.processor()}")
        info_lines.append(f"Архитектура: {platform.architecture()[0]}")

        # Информация о Steam Deck
        info_lines.append("")
        info_lines.append("--- Steam Deck ---")
        model = "неизвестна"
        for path in (
            "/sys/firmware/devicetree/base/model",
            "/proc/device-tree/model",
            "/sys/class/dmi/id/product_name"
        ):
            if os.path.isfile(path):
                try:
                    raw = open(path, "rb").read()
                    model = raw.decode('ascii', errors='ignore').rstrip('\x00').strip()
                    break
                except Exception:
                    continue

        # Маппинг кодовых имён
        if model == "Galileo":
            model_display = f"Steam Deck OLED ({model})"
        elif model == "Jupiter":
            model_display = f"Steam Deck LCD ({model})"
        else:
            model_display = model

        info_lines.append(f"Модель: {model_display}")

        # Версия SteamOS
        steamos_ver = "неизвестна"
        try:
            with open('/etc/os-release', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('VERSION_ID='):
                        steamos_ver = line.partition('=')[2].strip().strip('"')
                        break
        except:
            pass
        info_lines.append(f"SteamOS: {steamos_ver}")

        # Информация о диске
        if psutil:
            disk = psutil.disk_usage('/')
            info_lines.append("")
            info_lines.append("--- Диск ---")
            info_lines.append(f"Всего: {disk.total / (1024**3):.1f} GB")
            info_lines.append(f"Свободно: {disk.free / (1024**3):.1f} GB")
            info_lines.append(f"Использовано: {disk.used / (1024**3):.1f} GB")

        # Информация о приложении
        info_lines.append("")
        info_lines.append("--- Приложение ---")
        info_lines.append(f"Время запуска: {self.launch_time.strftime('%Y-%m-%d %H:%M:%S')}")
        info_lines.append(f"Лог-файл: {self.log_path}")

        return "\n".join(info_lines)

    def toggle_hw_info(self, on: bool):
        self.hw_container.setVisible(on)
        self.hw_btn.setText(f"Оборудование {'▼' if on else '▲'}")
        if on:
            self.update_hw_info()

    def update_hw_info(self):
        # 1) Читаем кодовое название модели
        model = "неизвестна"
        for path in (
            "/sys/firmware/devicetree/base/model",
            "/proc/device-tree/model",
            "/sys/class/dmi/id/product_name"
        ):
            if os.path.isfile(path):
                try:
                    raw = open(path, "rb").read()
                    model = raw.decode('ascii', errors='ignore').rstrip('\x00').strip()
                    break
                except Exception:
                    continue

        # 1.1) Маппинг кодовых имён в человекочитаемый формат
        if model == "Galileo":
            disp = f"Steam Deck OLED ({model})"
        elif model == "Jupiter":
            disp = f"Steam Deck LCD ({model})"
        else:
            disp = model
        self.lbl_steam_model.setText(f"Модель: {disp}")

        # 2) Версия SteamOS (читаем /etc/os-release)
        steamos_ver = "неизвестна"
        try:
            with open('/etc/os-release', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('VERSION_ID='):
                        steamos_ver = line.partition('=')[2].strip().strip('"')
                        break
        except:
            pass
        self.lbl_steamos.setText(f"Версия SteamOS: {steamos_ver}")

        # 3) Свободное место на /
        if psutil:
            free_gb = psutil.disk_usage('/').free / 1024**3
            self.lbl_free.setText(f"Свободно: {free_gb:.1f} ГБ")
        else:
            self.lbl_free.setText("Свободно: psutil не установлен")

        # 4) Время запуска
        self.lbl_launch.setText(f"Запущено: {self.launch_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 5) CPU и память процесса
        if psutil:
            cpu = psutil.cpu_percent()
            mem = psutil.Process().memory_info().rss / 1024**2
            self.lbl_cpu.setText(f"CPU: {cpu}%")
            self.lbl_mem.setText(f"Память: {mem:.1f} МБ")
        else:
            self.lbl_cpu.setText("CPU: psutil не установлен")
            self.lbl_mem.setText("Память: psutil не установлен")
