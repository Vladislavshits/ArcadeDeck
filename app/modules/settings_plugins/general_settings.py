import os
import subprocess
import json
import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QFrame, QSizePolicy
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, pyqtSignal

from settings import app_settings
from app.modules.module_logic.migration_dialog import MigrationDialog
from core import update_installation_paths, get_users_path

# Название модуля в логе
logger = logging.getLogger('Плагин общих настроек')

class PathToggleWidget(QFrame):
    """Виджет переключения пути установки игр"""
    pathChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        # Заголовок
        title = QLabel("Расположение папки users")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Контейнер для кнопок в одном ряду
        self.container = QFrame()
        self.container.setObjectName("PathButtonsFrame")

        container_layout = QHBoxLayout(self.container)
        container_layout.setContentsMargins(10, 10, 10, 20)
        container_layout.setSpacing(20)  # Сохраняем отступ 20px между кнопками

        # Кнопка "По умолчанию"
        self.default_btn = QPushButton("По умолчанию")
        self.default_btn.setObjectName("path_button")
        self.default_btn.setCheckable(True)
        self.default_btn.clicked.connect(lambda: self.select_path("default"))

        # Кнопка "SD-карта"
        self.sd_card_btn = QPushButton("SD-карта")
        self.sd_card_btn.setObjectName("path_button")
        self.sd_card_btn.setCheckable(True)
        self.sd_card_btn.clicked.connect(lambda: self.select_path("sd_card"))

        # Кнопка "Выбрать вручную"
        self.custom_btn = QPushButton("Выбрать вручную")
        self.custom_btn.setObjectName("path_button")
        self.custom_btn.setCheckable(True)
        self.custom_btn.clicked.connect(self.select_custom_path)

        # Добавляем кнопки в ряд
        container_layout.addWidget(self.default_btn)
        container_layout.addWidget(self.sd_card_btn)
        container_layout.addWidget(self.custom_btn)

        # Центрируем кнопки
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Метка текущего пути
        self.path_label = QLabel()
        self.path_label.setWordWrap(True)
        self.path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.path_label.setFont(QFont("Arial", 10))

        layout.addWidget(self.container)
        layout.addWidget(self.path_label)

        # Загружаем текущие настройки
        self.load_current_settings()

    def get_default_path(self):
        """Путь по умолчанию (в корне проекта)"""
        # Получаем корневую директорию проекта (ArcadeDeck/)
        project_root = Path(__file__).parent.parent.parent.parent
        return project_root / "users"

    def get_sd_card_path(self):
        """Путь к SD-карте на Steam Deck с автоматическим определением"""

        # Основной путь монтирования на Steam Deck
        base_path = Path("/run/media/deck")

        if base_path.exists():
            # Ищем все поддиректории в /run/media/deck/
            sd_cards = [d for d in base_path.iterdir() if d.is_dir()]

            if sd_cards:
                # Берем первую найденную SD-карту
                sd_card_path = sd_cards[0]

                # Проверяем, что это действительно съемное устройство
                try:
                    # Используем команду lsblk для проверки типа устройства
                    result = subprocess.run([
                        'lsblk', '-o', 'MOUNTPOINT,LABEL,FSTYPE,SIZE', '-J'
                    ], capture_output=True, text=True)

                    if result.returncode == 0:
                        import json
                        devices = json.loads(result.stdout)

                        # Ищем наше устройство в выводе lsblk
                        for device in devices.get('blockdevices', []):
                            if device.get('mountpoint') == str(sd_card_path):
                                # Это съемное устройство (SD-карта)
                                sd_path = sd_card_path / "ArcadeDeck" / "users"
                                return sd_path

                except Exception as e:
                    logger.warning(f"Не удалось проверить тип устройства: {e}")
                    # Если не удалось проверить, все равно используем найденный путь
                    sd_path = sd_card_path / "ArcadeDeck" / "users"
                    return sd_path

        # Альтернативные пути (для совместимости)
        alternative_paths = [
            "/run/media/mmcblk0p1",
            "/run/media/mmcblk1p1",
            "/run/media/mmcblk2p1",
        ]

        for path in alternative_paths:
            if os.path.exists(path):
                sd_path = Path(path) / "ArcadeDeck" / "users"
                return sd_path

        # Если SD-карта не найдена, показываем предупреждение
        QMessageBox.warning(
            self,
            "SD-карта не найдена",
            "SD-карта не обнаружена.\n\n"
            "Пожалуйста, проверьте:\n"
            "• Вставлена ли SD-карта в устройство\n"
            "• Определяется ли карта системой\n"
            "• Карта должна быть доступна по пути: /run/media/deck/[ИМЯ_КАРТЫ]/\n\n"
            "После подключения карты повторите выбор."
        )
        return None

    def load_current_settings(self):
        """Загружает текущие настройки пути"""
        current_path = app_settings.get_users_path()
        path_type = app_settings.get_users_path_type()

        # Обновляем метку
        self.path_label.setText(f"Текущий путь: {current_path}")

        # Устанавливаем активную кнопку
        self.default_btn.setChecked(path_type == "default")
        self.sd_card_btn.setChecked(path_type == "sd_card")
        self.custom_btn.setChecked(path_type == "custom")

    def select_path(self, path_type):
        """Выбирает путь установки"""
        if path_type == "default":
            path = self.get_default_path()
        elif path_type == "sd_card":
            path = self.get_sd_card_path()
            if path is None:
                # SD-карта не найдена, сбрасываем выбор
                self.load_current_settings()
                return
        else:
            return

        # Создаем целевую директорию
        path.mkdir(parents=True, exist_ok=True)

        # Получаем текущий путь из настроек
        current_path = Path(app_settings.get_users_path())

        # Проверяем, нужно ли выполнять миграцию
        migration_success = True
        if current_path != path and current_path.exists() and any(current_path.iterdir()):
            migration_success = self.migrate_data(current_path, path, path_type)

        # Если миграция не удалась, не меняем настройки
        if not migration_success:
            self.load_current_settings()
            return

        # Вместо прямого сохранения вызываем нашу функцию обновления
        self.update_users_path(str(path))  # ← ИЗМЕНИТЬ ЗДЕСЬ
        app_settings.set_users_path_type(path_type)  # ← Оставляем только тип пути

        # Обновляем интерфейс
        self.path_label.setText(f"Текущий путь: {path}")
        self.default_btn.setChecked(path_type == "default")
        self.sd_card_btn.setChecked(path_type == "sd_card")
        self.custom_btn.setChecked(False)

        # Открываем проводник для SD-карты
        if path_type == "sd_card":
            self.open_explorer(path)

        self.pathChanged.emit(str(path))

    def migrate_data(self, source_path, target_path, path_type):
        """Выполняет миграцию данных с подтверждением пользователя"""
        try:
            # Если текущий путь уже совпадает с целевым, не перемещаем
            if source_path == target_path:
                return True

            # Если в текущем пути нет данных, не перемещаем
            if not source_path.exists() or not any(source_path.iterdir()):
                return True

            # Спрашиваем подтверждение перемещения
            reply = QMessageBox.question(
                self,
                "Перемещение данных",
                f"Хотите автоматически переместить все данные?\n\n"
                f"Из: {source_path}\n"
                f"В: {target_path}\n\n"
                "Внимание: данные будут физически перемещены!",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )

            if reply != QMessageBox.StandardButton.Yes:
                return False  # Пользователь отказался

            # Запускаем диалог с прогрессом
            dialog = MigrationDialog(str(source_path), str(target_path), self)
            dialog.start_migration()  # Запускаем миграцию
            dialog.exec()

            # Проверяем результат миграции
            if dialog.worker and not dialog.worker.cancelled:
                # Проверяем, что файлы действительно переместились
                if target_path.exists() and any(target_path.iterdir()):
                    QMessageBox.information(
                        self,
                        "Перемещение завершено",
                        f"Данные успешно перемещены в:\n{target_path}"
                    )
                    return True
                else:
                    QMessageBox.warning(
                        self,
                        "Ошибка перемещения",
                        "Данные не были перемещены. Проверьте права доступа."
                    )
                    return False
            else:
                return False

        except Exception as e:
            logger.error(f"Ошибка при перемещении данных: {e}")
            QMessageBox.warning(
                self,
                "Ошибка перемещения",
                f"Не удалось переместить данные:\n{str(e)}"
            )
            return False

    def update_users_path(self, new_path):
        """Обновляет путь к пользовательским данным с обновлением installed_games.json и скриптов запуска"""
        try:
            old_path = get_users_path()
            logger.info(f"🔄 Обновление пути: {old_path} -> {new_path}")

            # Сохраняем новый путь в настройках
            app_settings.set_users_path(new_path)

            # Обновляем пути в installed_games.json и скриптах запуска
            success = update_installation_paths(old_path, new_path)

            if success:
                logger.info("✅ Путь пользовательских данных успешно обновлен")
                QMessageBox.information(
                    self,
                    "Успех",
                    f"Путь пользовательских данных изменен на:\n{new_path}\n\n"
                    f"Все пути к играм и скриптам запуска автоматически обновлены."
                )
            else:
                logger.error("❌ Не удалось обновить пути в installed_games.json или скриптах запуска")
                QMessageBox.warning(
                    self,
                    "Предупреждение",
                    f"Путь изменен, но некоторые пути к играм могут требовать ручного обновления."
                )

        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении пути: {e}")
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось обновить путь: {e}"
            )

    def open_explorer(self, path):
        """Открывает проводник в указанной папке"""
        try:
            import subprocess
            import platform
            import os

            # Проверяем существование пути
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)

            system = platform.system()

            if system == "Windows":
                subprocess.Popen(f'explorer "{path}"')
            elif system == "Darwin":  # macOS
                subprocess.Popen(['open', path])
            else:  # Linux (включая Steam Deck)
                # Попробуем разные файловые менеджеры
                file_managers = [
                    'dolphin',  # KDE (Steam Deck)
                    'nautilus', # GNOME
                    'thunar',   # XFCE
                    'pcmanfm',  # LXDE
                    'nemo'      # Cinnamon
                ]

                for manager in file_managers:
                    try:
                        subprocess.Popen([manager, path])
                        break
                    except FileNotFoundError:
                        continue
                else:
                    # Если не нашли файловый менеджер, используем xdg-open
                    subprocess.Popen(['xdg-open', path])

        except Exception as e:
            logger.error(f"Ошибка при открытии проводника: {e}")

    def select_custom_path(self):
        """Открывает диалог выбора пользовательского пути"""
        current_path = app_settings.get_users_path()

        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        dialog.setDirectory(str(current_path))

        if dialog.exec() == QFileDialog.DialogCode.Accepted:
            selected_path = dialog.selectedFiles()[0]
            custom_path = Path(selected_path) / "ArcadeDeck" / "users"

            # Создаем директорию
            custom_path.mkdir(parents=True, exist_ok=True)

            # Получаем текущий путь
            current_source_path = Path(app_settings.get_users_path())

            # Выполняем миграцию данных
            migration_success = True
            if current_source_path != custom_path and current_source_path.exists() and any(current_source_path.iterdir()):
                migration_success = self.migrate_data(current_source_path, custom_path, "custom")

            # Если миграция не удалась, не меняем настройки
            if not migration_success:
                self.load_current_settings()
                return

            # Вместо прямого сохранения вызываем нашу функцию обновления
            self.update_users_path(str(custom_path))  # ← ИЗМЕНИТЬ ЗДЕСЬ
            app_settings.set_users_path_type("custom")  # ← Оставляем только тип пути

            # Обновляем интерфейс
            self.path_label.setText(f"Текущий путь: {custom_path}")
            self.custom_btn.setChecked(True)
            self.default_btn.setChecked(False)
            self.sd_card_btn.setChecked(False)

            self.pathChanged.emit(str(custom_path))


class GeneralSettingsPage(QWidget):
    """Страница общих настроек"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        title = QLabel("Расположения файлов")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # Виджет выбора пути
        self.path_widget = PathToggleWidget()
        layout.addWidget(self.path_widget)

        # Информация о выборе пути
        info_label = QLabel(
            "Выберите расположение для папки users, в которой будут храниться "
            "игры, обложки и другие пользовательские данные.\n\n"
            "• По умолчанию - папка в директории программы\n"
            "• SD-карта - папка на SD-карте Steam Deck\n"
            "• Выбрать вручную - произвольное расположение"
        )
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        info_label.setFont(QFont("Arial", 10))
        layout.addWidget(info_label)

        layout.addStretch(1)
