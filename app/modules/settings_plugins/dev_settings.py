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
    QMessageBox, QFileDialog, QCheckBox, QSizePolicy
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer, QProcess
try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger(__name__)


class FocusButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setProperty("focused", False)

    def focusInEvent(self, event):
        self.setProperty("focused", True)
        self.style().unpolish(self)
        self.style().polish(self)
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.setProperty("focused", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().focusOutEvent(event)


class LogViewerDialog(QDialog):
    def __init__(self, log_path: str, parent=None, nav_controller=None):
        super().__init__(parent)

        self.nav_controller = nav_controller
        self.log_path = log_path

        self.auto_scroll = True
        self.last_file_position = 0

        self.nav_widgets = []
        self.current_nav_index = 0

        self.setWindowTitle("Просмотр логов")
        self.setModal(True)
        self.resize(1100, 700)

        self.init_ui()

        self.load_initial_logs()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.reload_logs)
        self.timer.start(1000)

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        title = QLabel("Просмотр логов")

        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        title.setFont(
            QFont("Arial", 18, QFont.Weight.Bold)
        )

        main_layout.addWidget(title)

        path_label = QLabel(
            f"Файл: {self.log_path}"
        )

        path_label.setWordWrap(True)

        path_label.setStyleSheet(
            "color: #888888; font-size: 13px;"
        )

        main_layout.addWidget(path_label)

        top_controls = QHBoxLayout()

        self.clear_button = FocusButton(
            "Очистить окно логов"
        )

        self.clear_button.clicked.connect(
            self.clear_logs
        )

        top_controls.addWidget(
            self.clear_button
        )

        self.auto_scroll_checkbox = QCheckBox(
            "Автопрокрутка"
        )

        self.auto_scroll_checkbox.setChecked(True)

        self.auto_scroll_checkbox.toggled.connect(
            self.set_auto_scroll
        )

        top_controls.addWidget(
            self.auto_scroll_checkbox
        )

        top_controls.addStretch()

        main_layout.addLayout(top_controls)

        self.log_text = QTextEdit()

        self.log_text.setReadOnly(True)

        self.log_text.setFont(
            QFont("Monospace", 10)
        )

        self.log_text.setLineWrapMode(
            QTextEdit.LineWrapMode.NoWrap
        )

        # Храним максимум 50 строк
        self.log_text.document().setMaximumBlockCount(
            50
        )

        main_layout.addWidget(
            self.log_text,
            1
        )

        bottom_layout = QHBoxLayout()

        bottom_layout.addStretch()

        self.close_button = FocusButton(
            "Закрыть"
        )

        self.close_button.clicked.connect(
            self.close_dialog
        )

        bottom_layout.addWidget(
            self.close_button
        )

        bottom_layout.addStretch()

        main_layout.addLayout(bottom_layout)

        self.nav_widgets = [
            self.clear_button,
            self.close_button
        ]

    def load_initial_logs(self):
        try:
            if not os.path.exists(
                self.log_path
            ):
                self.log_text.append(
                    "Лог-файл не найден."
                )
                return

            lines = []

            with open(
                self.log_path,
                "rb"
            ) as f:

                f.seek(0, os.SEEK_END)

                self.last_file_position = (
                    f.tell()
                )

                buffer = bytearray()

                pointer = (
                    self.last_file_position - 1
                )

                while (
                    pointer >= 0 and
                    len(lines) < 50
                ):
                    f.seek(pointer)

                    byte = f.read(1)

                    if byte == b'\n':
                        if buffer:
                            lines.append(
                                buffer[::-1].decode(
                                    "utf-8",
                                    errors="ignore"
                                )
                            )

                            buffer = bytearray()

                    else:
                        buffer.extend(byte)

                    pointer -= 1

                if buffer:
                    lines.append(
                        buffer[::-1].decode(
                            "utf-8",
                            errors="ignore"
                        )
                    )

            lines.reverse()

            for line in lines:
                clean_line = line.rstrip()

                if clean_line:
                    self.log_text.append(
                        clean_line
                    )

            scrollbar = (
                self.log_text.verticalScrollBar()
            )

            scrollbar.setValue(
                scrollbar.maximum()
            )

        except Exception:
            logger.exception(
                "Ошибка загрузки логов"
            )

    def reload_logs(self):
        try:
            if not os.path.exists(
                self.log_path
            ):
                return

            with open(
                self.log_path,
                "r",
                encoding="utf-8",
                errors="ignore"
            ) as f:

                f.seek(
                    self.last_file_position
                )

                new_lines = f.readlines()

                self.last_file_position = (
                    f.tell()
                )

            if not new_lines:
                return

            for line in new_lines:
                self.log_text.append(
                    line.rstrip()
                )

            if self.auto_scroll:
                scrollbar = (
                    self.log_text.verticalScrollBar()
                )

                scrollbar.setValue(
                    scrollbar.maximum()
                )

        except Exception:
            logger.exception(
                "Ошибка обновления логов"
            )

    def clear_logs(self):
        self.log_text.clear()

    def set_auto_scroll(self, enabled):
        self.auto_scroll = enabled

    def close_dialog(self):
        try:
            if self.timer:
                self.timer.stop()

        except Exception:
            logger.exception(
                "Ошибка остановки таймера"
            )

        self.close()

    def navigate_up(self):
        if not self.nav_widgets:
            return

        self.current_nav_index = (
            self.current_nav_index - 1
        ) % len(self.nav_widgets)

        self.update_focus()

    def navigate_down(self):
        if not self.nav_widgets:
            return

        self.current_nav_index = (
            self.current_nav_index + 1
        ) % len(self.nav_widgets)

        self.update_focus()

    def activate_current(self):
        if not self.nav_widgets:
            return

        widget = self.nav_widgets[
            self.current_nav_index
        ]

        if isinstance(widget, QPushButton):
            widget.click()

    def update_focus(self):
        for widget in self.nav_widgets:

            widget.setProperty(
                "focused",
                False
            )

            widget.style().unpolish(
                widget
            )

            widget.style().polish(
                widget
            )

        current = self.nav_widgets[
            self.current_nav_index
        ]

        current.setFocus()

        current.setProperty(
            "focused",
            True
        )

        current.style().unpolish(
            current
        )

        current.style().polish(
            current
        )

    def keyPressEvent(self, event):
        key = event.key()

        if key in (
            Qt.Key.Key_Up,
            Qt.Key.Key_Left
        ):
            self.navigate_up()
            return

        if key in (
            Qt.Key.Key_Down,
            Qt.Key.Key_Right
        ):
            self.navigate_down()
            return

        if key in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space
        ):
            self.activate_current()
            return

        if key == Qt.Key.Key_Escape:
            self.close_dialog()
            return

        super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)

        self.showMaximized()

        self.current_nav_index = 0

        self.update_focus()

        try:
            if (
                self.nav_controller and
                self.nav_widgets
            ):
                from navigation import (
                    NavigationLayer
                )

                self.nav_controller.add_managed_window(
                    self
                )

                self.nav_controller.set_dialog_open(
                    True
                )

                self.nav_controller.register_widgets(
                    NavigationLayer.DIALOG,
                    self.nav_widgets
                )

                self.nav_controller.switch_layer(
                    NavigationLayer.DIALOG
                )

        except Exception:
            logger.exception(
                "Ошибка showEvent"
            )

    def closeEvent(self, event):
        try:
            if self.timer:
                self.timer.stop()

            if self.nav_controller:
                from navigation import (
                    NavigationLayer
                )

                self.nav_controller.remove_managed_window(
                    self
                )

                self.nav_controller.set_dialog_open(
                    False
                )

                self.nav_controller.switch_layer(
                    NavigationLayer.SETTINGS
                )

        except Exception:
            logger.exception(
                "Ошибка closeEvent"
            )

        super().closeEvent(event)

class DevSettingsPage(QWidget):
    def __init__(self, parent=None, log_path: str = None):
        super().__init__(parent)
        from datetime import datetime
        self.launch_time = datetime.now()

        if log_path is None:
            try:
                if parent and hasattr(parent.window(), 'log_file'):
                    log_path = parent.window().log_file
                else:
                    log_path = os.path.join(os.path.expanduser("~"), "ArcadeDeck", "logs", "arcadedeck.log")
            except:
                log_path = os.path.join(os.path.expanduser("~"), "ArcadeDeck", "logs", "arcadedeck.log")
        self.log_path = str(log_path)
        log_dir = os.path.dirname(self.log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        self.focusable_widgets = []
        self.current_focus_index = 0
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("Инструменты разработчика")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        log_path_label = QLabel(f"Лог-файл: {self.log_path}")
        log_path_label.setStyleSheet("color: #888; font-size: 12px;")
        log_path_label.setWordWrap(True)
        layout.addWidget(log_path_label)

        # Уровень логирования
        hl = QHBoxLayout()
        hl.addWidget(QLabel("Уровень логирования:"))
        self.combo = QComboBox()
        self.combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        level_int = logging.getLogger().getEffectiveLevel()
        level_name = logging.getLevelName(level_int)
        self.combo.setCurrentText(level_name)
        self.combo.currentTextChanged.connect(self.on_level_changed)
        hl.addWidget(self.combo)
        layout.addLayout(hl)
        self.focusable_widgets.append(self.combo)

        log_buttons_layout = QHBoxLayout()
        self.btn_view = FocusButton("Открыть логи")
        self.btn_view.clicked.connect(self.open_log_viewer)
        log_buttons_layout.addWidget(self.btn_view)
        self.btn_archive = FocusButton("Создать архив логов")
        self.btn_archive.clicked.connect(self.create_logs_archive)
        log_buttons_layout.addWidget(self.btn_archive)
        layout.addLayout(log_buttons_layout)
        self.focusable_widgets.extend([self.btn_view, self.btn_archive])

        # Кнопка сброса данных (красный шрифт)
        self.btn_reset = FocusButton("Сброс данных программы")
        self.btn_reset.setStyleSheet("color: #ff4444; font-weight: bold;")
        self.btn_reset.clicked.connect(self.reset_app_data)
        layout.addWidget(self.btn_reset)
        self.focusable_widgets.append(self.btn_reset)

        self.hw_btn = FocusButton("Оборудование ▲")
        self.hw_btn.setCheckable(True)
        self.hw_btn.toggled.connect(self.toggle_hw_info)
        layout.addWidget(self.hw_btn)
        self.focusable_widgets.append(self.hw_btn)

        self.hw_container = QWidget()
        self.hw_container.hide()
        hw_layout = QVBoxLayout(self.hw_container)
        hw_layout.setContentsMargins(10, 5, 10, 5)
        self.lbl_steam_model = QLabel()
        self.lbl_steamos = QLabel()
        self.lbl_free = QLabel()
        self.lbl_launch = QLabel()
        self.lbl_cpu = QLabel()
        self.lbl_mem = QLabel()
        for lbl in (self.lbl_steam_model, self.lbl_steamos, self.lbl_free, self.lbl_launch, self.lbl_cpu, self.lbl_mem):
            hw_layout.addWidget(lbl)
        layout.addWidget(self.hw_container)

        layout.addStretch(1)
        self.hw_timer = QTimer(self)
        self.hw_timer.timeout.connect(self.update_hw_info)
        self.hw_timer.start(1000)

    def navigate_up(self):
        if self.focusable_widgets:
            self.current_focus_index = (self.current_focus_index - 1) % len(self.focusable_widgets)
            self._set_focus_on_current()
            return True
        return False

    def navigate_down(self):
        if self.focusable_widgets:
            self.current_focus_index = (self.current_focus_index + 1) % len(self.focusable_widgets)
            self._set_focus_on_current()
            return True
        return False

    def navigate_left(self):
        return False

    def navigate_right(self):
        return False

    def activate_current(self):
        if self.focusable_widgets and 0 <= self.current_focus_index < len(self.focusable_widgets):
            w = self.focusable_widgets[self.current_focus_index]
            if isinstance(w, QPushButton):
                QTimer.singleShot(0, w.click)
                return True
            elif isinstance(w, QComboBox):
                w.showPopup()
                return True
        return False

    def _set_focus_on_current(self):
        if self.focusable_widgets and 0 <= self.current_focus_index < len(self.focusable_widgets):
            for w in self.focusable_widgets:
                if hasattr(w, "setProperty"):
                    w.setProperty("focused", False)
                    w.style().unpolish(w)
                    w.style().polish(w)
                w.clearFocus()
            current = self.focusable_widgets[self.current_focus_index]
            if hasattr(current, "setProperty"):
                current.setProperty("focused", True)
                current.style().unpolish(current)
                current.style().polish(current)
            current.setFocus(Qt.FocusReason.TabFocusReason)

    def showEvent(self, event):
        self.current_focus_index = 0
        if self.focusable_widgets:
            self._set_focus_on_current()
        super().showEvent(event)

    def get_navigation_widgets(self):
        return self.focusable_widgets

    def on_level_changed(self, level):
        lvl = getattr(logging, level, logging.INFO)
        logging.getLogger().setLevel(lvl)

    def open_log_viewer(self):
        try:
            nav = None

            if hasattr(self.window(), 'navigation_controller'):
                nav = self.window().navigation_controller

            self.log_viewer_dialog = LogViewerDialog(
                self.log_path,
                parent=self.window(),
                nav_controller=nav
            )

            self.log_viewer_dialog.show()
            self.log_viewer_dialog.raise_()
            self.log_viewer_dialog.activateWindow()

        except Exception:
            logger.exception(
                "Ошибка открытия LogViewerDialog"
            )

    def create_logs_archive(self):
        try:
            logs_dir = os.path.dirname(self.log_path)
            if not os.path.exists(logs_dir):
                QMessageBox.warning(self, "Ошибка", "Директория логов не найдена")
                return
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"arcadedeck_logs_{timestamp}.zip"
            file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить архив логов", default_filename, "ZIP Archives (*.zip)")
            if not file_path:
                return
            with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(logs_dir):
                    for file in files:
                        if not file.endswith(('.tmp', '.zip')):
                            full = os.path.join(root, file)
                            arcname = os.path.relpath(full, logs_dir)
                            zipf.write(full, arcname)
                system_info = self._get_system_info()
                zipf.writestr("system_info.txt", system_info)
            archive_size = os.path.getsize(file_path) / 1024
            QMessageBox.information(self, "Архив создан", f"Архив логов успешно создан!\nФайл: {os.path.basename(file_path)}\nРазмер: {archive_size:.1f} KB\nПуть: {file_path}")
        except Exception as e:
            logger.error(f"Ошибка создания архива логов: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать архив логов:\n{str(e)}")

    def reset_app_data(self):
        """Сброс данных программы (заглушка)"""
        reply = QMessageBox.question(
            self,
            "Сброс данных программы",
            "Вы уверены, что хотите сбросить все данные программы?\n"
            "Будут удалены:\n"
            "- Все установленные игры\n"
            "- Настройки программы\n"
            "- Кэш обложек\n\n"
            "Это действие необратимо!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            logger.warning("Сброс данных программы (ещё не реализован)")
            QMessageBox.information(self, "Информация", "Функция сброса данных будет добавлена в следующем обновлении.")

    def _get_system_info(self):
        info = []
        info.append("=== ArcadeDeck System Information ===")
        info.append(f"Время сбора: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        info.append(f"Платформа: {platform.platform()}")
        info.append(f"Процессор: {platform.processor()}")
        info.append(f"Архитектура: {platform.architecture()[0]}")
        model = "неизвестна"
        for path in ("/sys/firmware/devicetree/base/model", "/proc/device-tree/model", "/sys/class/dmi/id/product_name"):
            if os.path.isfile(path):
                try:
                    raw = open(path, "rb").read()
                    model = raw.decode('ascii', errors='ignore').rstrip('\x00').strip()
                    break
                except:
                    continue
        if model == "Galileo":
            model_display = f"Steam Deck OLED ({model})"
        elif model == "Jupiter":
            model_display = f"Steam Deck LCD ({model})"
        else:
            model_display = model
        info.append(f"Модель: {model_display}")
        steamos_ver = "неизвестна"
        try:
            with open('/etc/os-release', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('VERSION_ID='):
                        steamos_ver = line.partition('=')[2].strip().strip('"')
                        break
        except:
            pass
        info.append(f"SteamOS: {steamos_ver}")
        if psutil:
            disk = psutil.disk_usage('/')
            info.append(f"Всего: {disk.total / (1024**3):.1f} GB")
            info.append(f"Свободно: {disk.free / (1024**3):.1f} GB")
            info.append(f"Использовано: {disk.used / (1024**3):.1f} GB")
        info.append(f"Время запуска: {self.launch_time.strftime('%Y-%m-%d %H:%M:%S')}")
        info.append(f"Лог-файл: {self.log_path}")
        return "\n".join(info)

    def toggle_hw_info(self, on):
        self.hw_container.setVisible(on)
        self.hw_btn.setText(f"Оборудование {'▼' if on else '▲'}")
        if on:
            self.update_hw_info()

    def update_hw_info(self):
        model = "неизвестна"
        for path in ("/sys/firmware/devicetree/base/model", "/proc/device-tree/model", "/sys/class/dmi/id/product_name"):
            if os.path.isfile(path):
                try:
                    raw = open(path, "rb").read()
                    model = raw.decode('ascii', errors='ignore').rstrip('\x00').strip()
                    break
                except:
                    continue
        if model == "Galileo":
            disp = f"Steam Deck OLED ({model})"
        elif model == "Jupiter":
            disp = f"Steam Deck LCD ({model})"
        else:
            disp = model
        self.lbl_steam_model.setText(f"Модель: {disp}")
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
        if psutil:
            free_gb = psutil.disk_usage('/').free / 1024**3
            self.lbl_free.setText(f"Свободно: {free_gb:.1f} ГБ")
        else:
            self.lbl_free.setText("Свободно: psutil не установлен")
        self.lbl_launch.setText(f"Запущено: {self.launch_time.strftime('%Y-%m-%d %H:%M:%S')}")
        if psutil:
            cpu = psutil.cpu_percent()
            mem = psutil.Process().memory_info().rss / 1024**2
            self.lbl_cpu.setText(f"CPU: {cpu}%")
            self.lbl_mem.setText(f"Память: {mem:.1f} МБ")
        else:
            self.lbl_cpu.setText("CPU: psutil не установлен")
            self.lbl_mem.setText("Память: psutil не установлен")