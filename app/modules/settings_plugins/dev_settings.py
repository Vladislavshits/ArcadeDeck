# app/modules/settings_plugins/dev_settings.py

import time
import platform
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QDialog, QTextEdit, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer
import logging
import os
try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger(__name__)

class LogViewerDialog(QDialog):
    """Окно просмотра лог-файла."""
    def __init__(self, log_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Просмотр логов")
        self.resize(800, 600)
        layout = QVBoxLayout(self)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)
        self.log_path = log_path
        # Обновлять раз в секунду
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.reload)
        self.timer.start(1000)
        self.reload()

    def reload(self):
        try:
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                data = f.read()
        except Exception as e:
            data = f"Не удалось прочитать лог: {e}"
        self.text.setPlainText(data)
        # скроллим вниз
        self.text.verticalScrollBar().setValue(self.text.verticalScrollBar().maximum())

class DevSettingsPage(QWidget):
    """Страница «Инструменты отладки»."""
    def __init__(self, parent=None, log_path: str = "app.log"):
        super().__init__(parent)
        from datetime import datetime
        self.launch_time = datetime.now()
        self.log_path = log_path
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20,20,20,20)
        layout.setSpacing(15)

        # 1) Уровень логирования
        hl = QHBoxLayout()
        hl.addWidget(QLabel("Log Level:"))
        self.combo = QComboBox()
        self.combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        
        # Правильно: получаем текстовое имя уровня из целочисленного кода
        level_int = logging.getLogger().getEffectiveLevel()
        level_name = logging.getLevelName(level_int)
        self.combo.setCurrentText(level_name)
        self.combo.currentTextChanged.connect(self.on_level_changed)
        hl.addWidget(self.combo)
        layout.addLayout(hl)

        # 2) Кнопка открытия логов
        btn_view = QPushButton("Открыть логи")
        btn_view.clicked.connect(self.open_log_viewer)
        layout.addWidget(btn_view, alignment=Qt.AlignmentFlag.AlignLeft)

        # 3) Кнопка «Оборудование» и скрытое окно с данными
        self.hw_btn = QPushButton("Оборудование ▲")
        self.hw_btn.setCheckable(True)
        self.hw_btn.toggled.connect(self.toggle_hw_info)
        layout.addWidget(self.hw_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self.hw_container = QWidget()
        self.hw_container.hide()
        hw_layout = QVBoxLayout(self.hw_container)
        hw_layout.setContentsMargins(10,5,10,5)

        # Информация о системе
        self.lbl_steam_model = QLabel()
        self.lbl_steamos     = QLabel()
        self.lbl_free        = QLabel()
        self.lbl_launch      = QLabel()
        self.lbl_cpu         = QLabel()
        self.lbl_mem         = QLabel()
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
        dlg = LogViewerDialog(self.log_path, parent=self.window())
        dlg.exec()

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
                    # многие device-tree файлы содержат нулевой байт в конце
                    raw = open(path, "rb").read()
                    model = raw.decode('ascii', errors='ignore').rstrip('\x00').strip()
                    break
                except Exception:
                    continue
        self.lbl_steam_model.setText(f"Модель: {model}")

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