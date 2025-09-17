import os
import shutil
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QMenu, QToolButton, QMessageBox, QFileDialog, QFrame
)
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtCore import Qt
from pathlib import Path
import logging
import json

logger = logging.getLogger('ArcadeDeck')

class GameInfoPage(QWidget):
    """Page for displaying game information"""
    def __init__(self, game_data=None, parent=None):
        super().__init__(parent)
        self.game_data = game_data

        # Initialize callbacks
        self._back_callback = None
        self._action_callback = None
        self._delete_callback = None
        self._change_cover_callback = None

        self._init_ui()

        # Initialize with game data if provided
        if game_data:
            self.set_game(game_data, is_installed=False)

    def _init_ui(self):
        """Initialize UI components"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(40)

        # Левая часть - обложка игры (увеличиваем размер)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Game cover - увеличенная плитка как в библиотеке
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(300, 450)  # Увеличиваем размер
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet("""
            border: 3px solid #444;
            border-radius: 15px;
            background-color: #2a2a2a;
        """)
        left_layout.addWidget(self.cover_label)
        left_layout.addStretch()

        # Правая часть - информация и кнопки
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        right_layout.setSpacing(25)

        # Контейнер для текстовой информации с выравниванием по левому краю
        text_container = QFrame()
        text_container_layout = QVBoxLayout(text_container)
        text_container_layout.setContentsMargins(0, 0, 0, 0)
        text_container_layout.setSpacing(15)
        text_container_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Game title - выравниваем по левому краю
        self.title_label = QLabel("Название игры")
        self.title_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #ffffff; margin: 0; padding: 0;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        text_container_layout.addWidget(self.title_label)

        # Game description - выравниваем по левому краю
        self.description_label = QLabel("Описание игры...")
        self.description_label.setWordWrap(True)
        self.description_label.setFont(QFont("Arial", 16))
        self.description_label.setStyleSheet("color: #cccccc; margin: 0; padding: 0;")
        self.description_label.setMinimumWidth(600)
        self.description_label.setMinimumHeight(150)
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        text_container_layout.addWidget(self.description_label)

        right_layout.addWidget(text_container)

        # Кнопки действий (располагаем снизу вверх)
        right_layout.addStretch()

        # Action buttons - вертикальное расположение
        self.action_button = QPushButton("Играть")
        self.action_button.setFixedHeight(60)
        self.action_button.setFont(QFont("Arial", 16, QFont.Weight.Bold))

        # Кнопка с контекстным меню
        self.menu_button = QToolButton()
        self.menu_button.setText("⋮")  # Три точки для меню
        self.menu_button.setFixedSize(70, 60)  # Увеличиваем размер
        self.menu_button.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_button.setStyleSheet("QToolButton::menu-indicator { image: none; }")

        # Создаем контекстное меню
        self.context_menu = QMenu(self.menu_button)

        # Действия меню
        self.delete_action = self.context_menu.addAction("Удалить игру")
        self.change_cover_action = self.context_menu.addAction("Изменить обложку")

        # Устанавливаем меню для кнопки
        self.menu_button.setMenu(self.context_menu)

        self.back_button = QPushButton("Назад в библиотеку")
        self.back_button.setFixedHeight(50)
        self.back_button.setFont(QFont("Arial", 14))

        # Горизонтальный layout для кнопок действия и меню
        action_layout = QHBoxLayout()
        action_layout.addWidget(self.action_button)
        action_layout.addWidget(self.menu_button)
        action_layout.setSpacing(10)

        # Добавляем кнопки в обратном порядке (снизу вверх)
        right_layout.addLayout(action_layout)
        right_layout.addWidget(self.back_button)

        # Добавляем левую и правую части в основной layout
        main_layout.addWidget(left_widget, 45)  # 45% ширины для обложки
        main_layout.addWidget(right_widget, 55)  # 55% ширины для информации

        # Connect signals
        self.back_button.clicked.connect(self.on_back)
        self.action_button.clicked.connect(self.on_action)
        self.delete_action.triggered.connect(self.on_delete)
        self.change_cover_action.triggered.connect(self.on_change_cover)

    def update_installation_status(self, is_installed):
        """Обновить кнопки в зависимости от статуса установки"""
        self.is_installed = is_installed
        self.action_button.setText("Играть" if self.is_installed else "Установить")

        # Показываем/скрываем кнопку меню в зависимости от статуса установки
        self.menu_button.setVisible(self.is_installed)

        # Включаем/выключаем действия меню
        self.delete_action.setEnabled(self.is_installed)
        self.change_cover_action.setEnabled(self.is_installed)

    def set_game(self, game_data, is_installed=False):
        """Set game data to display"""
        self.game_data = game_data or {}
        self.is_installed = bool(is_installed)

        # Обновить название игры
        self.title_label.setText(
            self.game_data.get("title", "Без названия")
        )

        # Обновить описание игры
        self.description_label.setText(
            self.game_data.get("description", "Нет описания")
        )

        # Обновить обложку игры
        self.update_cover_image()

        # Обновить кнопки
        self.action_button.setText("Играть" if self.is_installed else "Установить")
        self.menu_button.setVisible(self.is_installed)
        self.delete_action.setEnabled(self.is_installed)
        self.change_cover_action.setEnabled(self.is_installed)

    def update_cover_image(self):
        """Обновить изображение обложки"""
        logger.info(f"🖼️ Обновление обложки для игры: {self.game_data.get('title')}")

        # Пытаемся найти обложку в пользовательской папке
        custom_cover_path = self.get_custom_cover_path()

        if custom_cover_path and os.path.exists(custom_cover_path):
            logger.info(f"✅ Используется пользовательская обложка: {custom_cover_path}")
            try:
                pixmap = QPixmap(custom_cover_path)
                if pixmap.isNull():
                    logger.warning(f"⚠️ Не удалось загрузить пользовательскую обложку: {custom_cover_path}")
                    raise Exception("Invalid image file")
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки пользовательской обложки: {e}")
                custom_cover_path = None

        if not custom_cover_path:
            # Используем стандартную обложку из данных игры
            image_path = self.game_data.get("image_path")
            if image_path and os.path.exists(image_path):
                logger.info(f"📋 Используется стандартная обложка: {image_path}")
                try:
                    pixmap = QPixmap(image_path)
                    if pixmap.isNull():
                        logger.warning(f"⚠️ Не удалось загрузить стандартную обложку: {image_path}")
                        raise Exception("Invalid image file")
                except Exception as e:
                    logger.error(f"❌ Ошибка загрузки стандартной обложки: {e}")
                    self.cover_label.clear()
                    return
            else:
                # Очищаем, если обложки нет
                logger.warning(f"⚠️ Обложка не найдена для игры: {self.game_data.get('title')}")
                self.cover_label.clear()
                return

        # Масштабируем и устанавливаем обложку
        self.cover_label.setPixmap(pixmap.scaled(
            self.cover_label.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        ))
        logger.info(f"✅ Обложка успешно обновлена")

    def get_custom_cover_path(self):
        """Получить путь к пользовательской обложке игры"""
        if not self.game_data:
            logger.warning("⚠️ Нет данных игры для поиска обложки")
            return None

        game_id = self.game_data.get('id')
        platform = self.game_data.get('platform')

        if not all([game_id, platform]):
            logger.warning(f"⚠️ Неполные данные игры для поиска обложки: game_id={game_id}, platform={platform}")
            return None

        # Получаем project_root из родительского окна или используем относительный путь
        try:
            # Предполагаем, что главное окно имеет атрибут project_root
            project_root = self.window().project_root
        except AttributeError:
            # Fallback: используем относительный путь
            project_root = Path(".")

        # Формируем правильный путь: {project_root}/users/images/{platform}/{game_id}/
        images_dir = project_root / "users" / "images" / platform / game_id
        logger.info(f"🔍 Поиск обложки в: {images_dir}")

        # Создаем директорию, если её нет
        try:
            images_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Директория для обложек создана/проверена: {images_dir}")
        except Exception as e:
            logger.error(f"❌ Ошибка создания директории для обложек: {e}")
            return None

        # Ищем файлы изображений в директории
        image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.webp']
        for ext in image_extensions:
            cover_path = images_dir / f"cover{ext}"
            if cover_path.exists():
                logger.info(f"✅ Найдена обложка: {cover_path}")
                return str(cover_path)

        logger.info(f"📭 Пользовательская обложка не найдена в: {images_dir}")
        return None

    def on_change_cover(self):
        """Handle change cover action from menu"""
        if not self.game_data:
            logger.warning("⚠️ Попытка изменить обложку без данных игры")
            return

        logger.info(f"🎨 Запрос на изменение обложки для игры: {self.game_data.get('title')}")

        # Открываем диалог выбора файла
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите новую обложку",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )

        if not file_path:
            logger.info("👤 Пользователь отменил выбор обложки")
            return  # Пользователь отменил выбор

        # Проверяем формат файла
        valid_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.webp']
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in valid_extensions:
            logger.warning(f"⚠️ Неверный формат файла: {file_ext}")
            QMessageBox.warning(
                self,
                "Неверный формат",
                f"Пожалуйста, выберите изображение в одном из форматов: {', '.join(valid_extensions)}"
            )
            return

        try:
            # Создаем структуру папок для обложки
            game_id = self.game_data.get('id')
            platform = self.game_data.get('platform')

            if not game_id or not platform:
                logger.error("❌ Не удалось определить ID игры или платформу")
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    "Не удалось определить ID игры или платформу"
                )
                return

            # Получаем project_root
            try:
                project_root = self.window().project_root
            except AttributeError:
                project_root = Path(".")

            # Создаем папку для обложки: {project_root}/users/images/{platform}/{game_id}/
            cover_dir = project_root / "users" / "images" / platform / game_id
            cover_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Создана директория для обложки: {cover_dir}")

            # Сохраняем обложку с именем cover.{расширение}
            cover_filename = f"cover{file_ext}"
            destination_path = cover_dir / cover_filename

            # Удаляем старые обложки с другими расширениями
            for old_ext in valid_extensions:
                if old_ext != file_ext:
                    old_path = cover_dir / f"cover{old_ext}"
                    if old_path.exists():
                        old_path.unlink()
                        logger.info(f"🗑️ Удалена старая обложка: {old_path}")

            # Копируем файл
            shutil.copy2(file_path, destination_path)
            logger.info(f"✅ Обложка сохранена: {destination_path}")

            # Обновляем отображение
            self.update_cover_image()

            # Сохраняем путь к папке с обложками в реестре
            self._update_registry_with_cover_path(str(cover_dir))

            # Вызываем callback с новым путем к обложке
            if self.change_cover_callback:
                self.change_cover_callback(self.game_data, str(destination_path))

            # Показываем уведомление об успехе
            QMessageBox.information(
                self,
                "Успех! 🎉",
                "Обложка успешно обновлена!\n\n"
                f"Файл: {cover_filename}\n"
                f"Путь: {cover_dir}"
            )
            logger.info(f"✅ Обложка успешно изменена и уведомление показано")

        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении обложки: {e}")
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось сохранить обложку:\n{str(e)}"
            )

    def _update_registry_with_cover_path(self, cover_dir_path):
        """Обновить реестр установленных игр с путем к папке обложек"""
        try:
            game_id = self.game_data.get('id')
            if not game_id:
                return

            # Получаем project_root
            try:
                project_root = self.window().project_root
            except AttributeError:
                project_root = Path(".")

            # Путь к реестру установленных игр
            registry_path = project_root / "users" / "installed_games.json"

            if not registry_path.exists():
                return

            # Читаем реестр
            with open(registry_path, 'r', encoding='utf-8') as f:
                registry = json.load(f)

            # Обновляем запись игры
            for game in registry.get('installed_games', []):
                if game.get('id') == game_id:
                    game['cover_directory'] = cover_dir_path
                    break

            # Сохраняем обновленный реестр
            with open(registry_path, 'w', encoding='utf-8') as f:
                json.dump(registry, f, ensure_ascii=False, indent=4)

            logger.info(f"✅ Реестр обновлен с путем к обложкам: {cover_dir_path}")

        except Exception as e:
            logger.error(f"❌ Ошибка обновления реестра: {e}")

    def _delete_game_files(self, game_data):
        """Удалить все файлы игры на основе данных из реестра"""
        try:
            # Получаем актуальные данные из реестра установленных игр
            try:
                project_root = self.window().project_root
            except AttributeError:
                project_root = Path(".")

            registry_path = project_root / "users" / "installed_games.json"

            if not registry_path.exists():
                logger.warning("⚠️ Реестр установленных игр не найден")
                return

            # Читаем реестр
            with open(registry_path, 'r', encoding='utf-8') as f:
                registry = json.load(f)

            # Ищем игру в реестре (ваша структура)
            game_id = game_data.get('id')
            game_info = registry.get(game_id)

            if not game_info:
                logger.warning(f"⚠️ Игра {game_id} не найдена в реестре")
                return

            # Удаляем файлы на основе данных из реестра
            paths_to_delete = [
                game_info.get('install_path'),      # Файл игры
                game_info.get('launcher_path'),     # Скрипт запуска
            ]

            for path_str in paths_to_delete:
                if path_str and os.path.exists(path_str):
                    path_obj = Path(path_str)
                    if path_obj.is_file():
                        path_obj.unlink()
                        logger.info(f"🗑️ Удален файл: {path_str}")
                    elif path_obj.is_dir():
                        shutil.rmtree(path_obj)
                        logger.info(f"🗑️ Удалена папка: {path_str}")

            # Удаляем папку с обложками игры
            cover_dir = project_root / "users" / "images" / game_info.get('platform') / game_id
            if cover_dir.exists() and cover_dir.is_dir():
                shutil.rmtree(cover_dir)
                logger.info(f"🗑️ Удалена папка с обложками: {cover_dir}")

            # Дополнительно удаляем скрипт запуска из папки launchers
            launcher_path = project_root / "users" / "launchers" / f"{game_id}.sh"
            if launcher_path.exists():
                launcher_path.unlink()
                logger.info(f"🗑️ Удален скрипт запуска: {launcher_path}")

        except Exception as e:
            logger.error(f"❌ Ошибка удаления файлов игры: {e}")
            raise

    def _remove_from_registry(self, game_data):
        """Удалить игру из реестра установленных игр"""
        try:
            game_id = game_data.get('id')
            if not game_id:
                return

            # Получаем project_root
            try:
                project_root = self.window().project_root
            except AttributeError:
                project_root = Path(".")

            # Путь к реестру установленных игр
            registry_path = project_root / "users" / "installed_games.json"

            if not registry_path.exists():
                return

            # Читаем реестр
            with open(registry_path, 'r', encoding='utf-8') as f:
                registry = json.load(f)

            # Удаляем игру из реестра (ваша структура)
            if game_id in registry:
                del registry[game_id]
                logger.info(f"✅ Игра удалена из реестра: {game_id}")

                # Если реестр пустой (только installed_games массив), удаляем файл
                if len(registry) == 1 and "installed_games" in registry and not registry["installed_games"]:
                    os.remove(registry_path)
                    logger.info("🗑️ Удален файл реестра (последняя игра)")
                else:
                    # Сохраняем обновленный реестр
                    with open(registry_path, 'w', encoding='utf-8') as f:
                        json.dump(registry, f, ensure_ascii=False, indent=4)

        except Exception as e:
            logger.error(f"❌ Ошибка удаления из реестра: {e}")
            raise

    def load_game(self, game_data):
        """
        Загружает данные игры и отображает их на странице.
        Использует централизованный менеджер для актуальных данных.
        """
        if not game_data:
            return

        try:
            # Получаем актуальные данные из централизованного менеджера
            game_id = game_data.get('id')
            if game_id:
                from app.modules.module_logic.game_data_manager import get_game_data_manager
                manager = get_game_data_manager()

                if manager:
                    actual_game_data = manager.get_game_by_id(game_id)
                    if actual_game_data:
                        game_data = actual_game_data

            # Устанавливаем данные игры
            is_installed_status = game_data.get('is_installed', False)
            self.set_game(game_data, is_installed_status)

        except Exception as e:
            logger.error(f"Ошибка загрузки данных игры: {e}")
            # Используем переданные данные как fallback
            is_installed_status = game_data.get('is_installed', False)
            self.set_game(game_data, is_installed_status)

    def on_back(self):
        """Handle back button click"""
        if self.back_callback:
            self.back_callback()

    def on_action(self):
        """Handle action button click"""
        if self.action_callback:
            self.action_callback(self.game_data, self.is_installed)

    def on_delete(self):
        """Handle delete action from menu"""
        if not self.game_data:
            return

        game_title = self.game_data.get("title", "эту игру")
        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Вы уверены, что хотите удалить '{game_title}'?\n\n"
            "Будут удалены:\n"
            "• Файл игры\n"
            "• Скрипт запуска\n"
            "• Папка с обложками\n"
            "• Запись в реестре",
            QMessageBox.StandardButton.No | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Сначала удаляем файлы игры
                self._delete_game_files(self.game_data)

                # Затем удаляем из реестра
                self._remove_from_registry(self.game_data)

                # Обновляем статус установки в реальном времени
                self.is_installed = False
                self.update_installation_status(False)

                # Очищаем обложку
                self.cover_label.clear()

                # Вызываем callback для обновления UI
                if self.delete_callback:
                    self.delete_callback(self.game_data)

                QMessageBox.information(
                    self,
                    "Успех",
                    f"Игра '{game_title}' успешно удалена!"
                )

            except Exception as e:
                logger.error(f"❌ Ошибка при удалении игры: {e}")
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    f"Не удалось полностью удалить игру:\n{str(e)}"
                )

    # Properties for callbacks
    @property
    def back_callback(self):
        return self._back_callback

    @back_callback.setter
    def back_callback(self, callback):
        self._back_callback = callback

    @property
    def action_callback(self):
        return self._action_callback

    @action_callback.setter
    def action_callback(self, callback):
        self._action_callback = callback

    @property
    def delete_callback(self):
        return self._delete_callback

    @delete_callback.setter
    def delete_callback(self, callback):
        self._delete_callback = callback

    @property
    def change_cover_callback(self):
        return self._change_cover_callback

    @change_cover_callback.setter
    def change_cover_callback(self, callback):
        self._change_cover_callback = callback
