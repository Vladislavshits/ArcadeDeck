# app/modules/settings_plugins/dev_settings.py

import time
import platform
import logging
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QDialog, QTextEdit, QScrollArea, QRadioButton
)
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


class InstallerLogDialog(QDialog):
    """Окно, показывающее stdout/stderr процесса установки в реальном времени."""
    def __init__(self, cmd_args: list, workdir: str = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Установка — лог в реальном времени")
        self.resize(900, 600)
        self.workdir = workdir

        layout = QVBoxLayout(self)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)

        # Процесс
        self.proc = QProcess(self)
        if workdir:
            self.proc.setWorkingDirectory(workdir)
        self.proc.readyReadStandardOutput.connect(self._on_stdout)
        self.proc.readyReadStandardError.connect(self._on_stderr)
        self.proc.finished.connect(self._on_finished)

        try:
            # cmd_args = ["python3", "app/modules/installer/auto_installer.py", "--mode=test"]
            program = cmd_args[0]
            args = cmd_args[1:]
            self.append_line(f"[CMD] {program} {' '.join(args)}\n")
            self.proc.start(program, args)
        except Exception as e:
            self.append_line(f"[ERROR] Не удалось запустить процесс: {e}")

    def append_line(self, txt: str):
        # добавляем текст и скроллим вниз
        self.text.append(txt)
        self.text.verticalScrollBar().setValue(self.text.verticalScrollBar().maximum())

    def _on_stdout(self):
        try:
            out = bytes(self.proc.readAllStandardOutput()).decode('utf-8', errors='replace')
        except Exception:
            out = "<не удалось прочитать stdout>"
        if out:
            self.append_line(out)

    def _on_stderr(self):
        try:
            err = bytes(self.proc.readAllStandardError()).decode('utf-8', errors='replace')
        except Exception:
            err = "<не удалось прочитать stderr>"
        if err:
            # выделяем ошибки красным (HTML), QTextEdit может отобразить их
            self.append_line(f"<span style='color:red'>{err}</span>")

    def _on_finished(self):
        self.append_line("\n=== Процесс завершён ===")


class DevSettingsPage(QWidget):
    """Страница «Инструменты отладки» с запуском инсталлятора."""
    def __init__(self, parent=None, log_path: str = "app.log"):
        super().__init__(parent)
        from datetime import datetime
        self.launch_time = datetime.now()
        self.log_path = log_path
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
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

        # 4) --- НОВЫЙ БЛОК: запуск инсталлятора (тест/боевой) ---
        blk = QHBoxLayout()
        self.radio_test = QRadioButton("Тестовый режим")
        self.radio_live = QRadioButton("Боевой режим")
        self.radio_test.setChecked(True)
        blk.addWidget(QLabel("Режим установки:"))
        blk.addWidget(self.radio_test)
        blk.addWidget(self.radio_live)
        layout.addLayout(blk)

        run_layout = QHBoxLayout()
        self.run_btn = QPushButton("Запустить установку")
        self.run_btn.clicked.connect(self.on_run_installer)
        run_layout.addWidget(self.run_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # кнопка для открытия отдельного диалога логов (несколько вариантов)
        self.open_installer_log_btn = QPushButton("Открыть текущий лог установки")
        self.open_installer_log_btn.clicked.connect(self.open_auto_install_log)
        run_layout.addWidget(self.open_installer_log_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addLayout(run_layout)

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

    # --- Новые методы для запуска инсталлятора и логов ---
    def on_run_installer(self):
        """
        Запуск автоинсталлятора в выбранном режиме.
        Открываем окно InstallerLogDialog, который подхватывает stdout/stderr.
        """
        mode = "test" if self.radio_test.isChecked() else "live"
        # передаём команду: python3 app/modules/installer/auto_installer.py --mode=test
        cmd = ["python3", "app/modules/installer/auto_installer.py", f"--mode={mode}"]
        workdir = str(Path(__file__).resolve().parents[3])  # корень проекта
        dlg = InstallerLogDialog(cmd, workdir=workdir, parent=self.window())
        dlg.exec()

    def open_auto_install_log(self):
        """
        Открывает статическое окно просмотра файла logs/auto_install.log (в реальном времени обновляет содержимое).
        """
        logpath = str(Path(__file__).resolve().parents[3] / "logs" / "auto_install.log")
        dlg = LogViewerDialog(logpath, parent=self.window())
        dlg.exec()
