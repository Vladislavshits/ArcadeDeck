import os
import shutil
import logging
import json

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QMenu, QToolButton, QMessageBox, QFileDialog, QFrame,
    QGridLayout
)
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtCore import Qt
from pathlib import Path

# Импорт пути игровых данных
from core import get_users_path

logger = logging.getLogger('ArcadeDeck')

class GameInfoPage(QWidget):
    """Page for displaying game information - PS5 Style Minimalistic"""
    def __init__(self, game_data=None, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self.is_installed = False

        # Initialize callbacks
        self._back_callback = None
        self._action_callback = None
        self._delete_callback = None
        self._change_cover_callback = None

        self._init_ui()

        if game_data:
            self.set_game(game_data, is_installed=False)

    def _init_ui(self):
        """Initialize PS5 style minimalistic UI"""
        # Основной фон
        self.setStyleSheet("""
            GameInfoPage {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #000000, stop:0.3 #1a1a1a, stop:1 #2d2d2d);
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 30, 40, 30)
        main_layout.setSpacing(0)

        # Главная карточка
        main_card = QFrame()
        main_card.setStyleSheet("""
            QFrame {
                background: rgba(20, 20, 20, 0.95);
                border-radius: 20px;
                border: 1px solid #333;
            }
        """)

        card_layout = QVBoxLayout(main_card)
        card_layout.setContentsMargins(30, 25, 30, 25)
        card_layout.setSpacing(20)

        # Основной контент - горизонтальное расположение
        content_layout = QHBoxLayout()
        content_layout.setSpacing(40)

        # Левая часть - обложка
        left_cover_widget = self._create_cover_section()
        content_layout.addWidget(left_cover_widget)

        # Правая часть - информация и кнопки
        right_info_widget = self._create_info_section()
        content_layout.addWidget(right_info_widget)

        card_layout.addLayout(content_layout)
        main_layout.addWidget(main_card)

    def _create_cover_section(self):
        """Создает левую секцию с обложкой"""
        cover_widget = QFrame()
        cover_widget.setStyleSheet("QFrame { background: transparent; }")
        cover_layout = QVBoxLayout(cover_widget)
        cover_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Обложка игры (адаптивный размер)
        self.cover_label = QLabel()
        self.cover_label.setMinimumSize(300, 450)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet("""
            QLabel {
                background: #1a1a1a;
                border-radius: 15px;
                border: 2px solid #444;
            }
        """)
        cover_layout.addWidget(self.cover_label)

        return cover_widget

    def _create_info_section(self):
        """Создает правую секцию с информацией и кнопками"""
        info_widget = QFrame()
        info_widget.setStyleSheet("QFrame { background: transparent; }")
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(25)

        # Название игры (БЕЗ ВЕРХНЕГО РЕГИСТРА)
        self.title_label = QLabel("Grand Theft Auto: San Andreas")
        self.title_label.setFont(QFont("Arial", 32, QFont.Weight.Bold))
        self.title_label.setStyleSheet("""
            color: #ffffff;
            padding: 0;
            margin: 0;
            background: transparent;
        """)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.title_label.setWordWrap(True)
        info_layout.addWidget(self.title_label)

        # Описание игры
        self.description_label = QLabel("Загрузка описания...")
        self.description_label.setWordWrap(True)
        self.description_label.setFont(QFont("Arial", 16))
        self.description_label.setStyleSheet("""
            color: #cccccc;
            line-height: 1.6;
            padding: 0;
            margin: 0;
            background: transparent;
        """)
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.description_label.setMinimumHeight(150)
        info_layout.addWidget(self.description_label)

        # Панель метаданных (ПОД ОПИСАНИЕМ)
        meta_panel = self._create_meta_panel()
        info_layout.addWidget(meta_panel)

        info_layout.addStretch()

        # Панель кнопок
        button_panel = self._create_button_panel()
        info_layout.addWidget(button_panel)

        return info_widget

    def _create_meta_panel(self):
        """Создает панель метаданных"""
        meta_panel = QFrame()
        meta_panel.setStyleSheet("""
            QFrame {
                background: rgba(30, 30, 30, 0.8);
                border-radius: 12px;
                padding: 15px;
                margin: 10px 0;
            }
        """)

        meta_layout = QGridLayout(meta_panel)
        meta_layout.setHorizontalSpacing(20)
        meta_layout.setVerticalSpacing(10)
        meta_layout.setContentsMargins(10, 10, 10, 10)

        # Метаданные в 2 колонки для лучшего отображения на Steam Deck
        self.year_label = self._create_meta_label("📅 Год: —")
        self.language_label = self._create_meta_label("🌐 Язык: —")
        self.platform_label = self._create_meta_label("🎮 Платформа: —")
        self.size_label = self._create_meta_label("💾 Размер: —")
        self.rating_label = self._create_meta_label("⭐ Рейтинг: —")
        self.developer_label = self._create_meta_label("👨‍💻 Разработчик: —")
        self.genre_label = self._create_meta_label("🎭 Жанр: —")

        # Распределяем по 2 колонкам для лучшего отображения
        meta_layout.addWidget(self.platform_label, 0, 0)
        meta_layout.addWidget(self.size_label, 0, 1)
        meta_layout.addWidget(self.year_label, 1, 0)
        meta_layout.addWidget(self.rating_label, 1, 1)
        meta_layout.addWidget(self.language_label, 2, 0)
        meta_layout.addWidget(self.genre_label, 2, 1)
        meta_layout.addWidget(self.developer_label, 3, 0, 1, 2)  # Занимает обе колонки

        return meta_panel

    def _create_meta_label(self, text):
        """Создает метку для метаданных с оптимальными настройками"""
        label = QLabel(text)
        label.setFont(QFont("Arial", 12))
        label.setStyleSheet("""
            QLabel {
                color: #e0e0e0;
                background: transparent;
                padding: 8px 5px;
                margin: 0;
            }
        """)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setWordWrap(True)
        label.setMinimumHeight(35)
        return label

    def _create_button_panel(self):
        """Создает панель кнопок"""
        button_panel = QFrame()
        button_panel.setStyleSheet("QFrame { background: transparent; }")

        button_layout = QHBoxLayout(button_panel)
        button_layout.setSpacing(15)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Основная кнопка действия
        self.action_button = QPushButton("ИГРАТЬ")
        self.action_button.setMinimumSize(180, 60)
        self.action_button.setFont(QFont("Arial", 16, QFont.Weight.Bold))

        # Кнопка меню
        self.menu_button = QToolButton()
        self.menu_button.setText("⚙")
        self.menu_button.setMinimumSize(70, 60)
        self.menu_button.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        # Контекстное меню
        self.context_menu = QMenu(self.menu_button)
        self.context_menu.setStyleSheet("""
            QMenu {
                background: #2a2a2a;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 8px;
            }
            QMenu::item {
                padding: 12px 25px;
                border-radius: 6px;
                color: #ddd;
                font-size: 14px;
            }
            QMenu::item:selected {
                background: rgba(0, 122, 204, 0.3);
            }
        """)

        self.delete_action = self.context_menu.addAction("🗑️ Удалить игру")
        self.change_cover_action = self.context_menu.addAction("🎨 Изменить обложку")
        self.menu_button.setMenu(self.context_menu)

        # Кнопка назад
        self.back_button = QPushButton("НАЗАД")
        self.back_button.setMinimumSize(140, 60)
        self.back_button.setFont(QFont("Arial", 14, QFont.Weight.Bold))

        button_layout.addWidget(self.action_button)
        button_layout.addWidget(self.menu_button)
        button_layout.addWidget(self.back_button)

        # Connect signals
        self.back_button.clicked.connect(self.on_back)
        self.action_button.clicked.connect(self.on_action)
        self.delete_action.triggered.connect(self.on_delete)
        self.change_cover_action.triggered.connect(self.on_change_cover)

        return button_panel

    def _update_action_button_style(self):
        """Обновляет стиль кнопки действия в зависимости от статуса"""
        if not hasattr(self, 'is_installed'):
            self.is_installed = False

        if self.is_installed:
            style = """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #007acc, stop:1 #005a9e);
                    color: white;
                    border: none;
                    border-radius: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #0098ff, stop:1 #007acc);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #005a9e, stop:1 #004a80);
                }
            """
        else:
            style = """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #4CAF50, stop:1 #45a049);
                    color: white;
                    border: none;
                    border-radius: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #5CBF60, stop:1 #55B059);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3D8B40, stop:1 #368039);
                }
            """
        self.action_button.setStyleSheet(style)

    def set_game(self, game_data, is_installed=False):
        """Set game data to display with enhanced metadata"""
        self.game_data = game_data or {}
        self.is_installed = bool(is_installed)

        # Основные данные (БЕЗ ВЕРХНЕГО РЕГИСТРА)
        self.title_label.setText(self.game_data.get("title", "Без названия"))
        self.description_label.setText(self.game_data.get("description", "Нет описания"))

        # Метаданные
        self.year_label.setText(f"📅 Год: {self.game_data.get('year', '—')}")
        self.language_label.setText(f"🌐 Язык: {self.game_data.get('language', '—')}")
        self.platform_label.setText(f"🎮 Платформа: {self.game_data.get('platform', '—')}")

        # Форматирование размера
        size_bytes = self.game_data.get('size_bytes')
        size_display = self._format_size(size_bytes) if size_bytes else self.game_data.get('size', '—')
        self.size_label.setText(f"💾 Размер: {size_display}")

        self.rating_label.setText(f"⭐ Рейтинг: {self.game_data.get('rating', '—')}")
        self.developer_label.setText(f"👨‍💻 Разработчик: {self.game_data.get('developer', '—')}")
        self.genre_label.setText(f"🎭 Жанр: {self.game_data.get('genre', '—')}")

        # Обновить обложку и кнопки
        self.update_cover_image()
        self.update_installation_status(self.is_installed)

    def resizeEvent(self, event):
        """Обработчик изменения размера окна"""
        super().resizeEvent(event)
        self._adapt_to_screen_size()

    def _adapt_to_screen_size(self):
        """Адаптирует интерфейс к размеру экрана"""
        screen_width = self.width()

        # Адаптивные размеры в зависимости от ширины экрана
        if screen_width < 1280:
            # Маленький экран (Steam Deck портретный режим)
            cover_width = 280
            title_font_size = 24
            desc_font_size = 14
            meta_font_size = 11  # Уменьшен для Steam Deck
            button_height = 50
            main_margins = (20, 20, 20, 20)
            meta_padding = "10px"  # Меньше padding для маленьких экранов
        elif screen_width < 1920:
            # Средний экран
            cover_width = 350
            title_font_size = 28
            desc_font_size = 15
            meta_font_size = 12
            button_height = 55
            main_margins = (30, 25, 30, 25)
            meta_padding = "12px"
        else:
            # Большой экран
            cover_width = 400
            title_font_size = 32
            desc_font_size = 16
            meta_font_size = 13
            button_height = 60
            main_margins = (40, 30, 40, 30)
            meta_padding = "15px"

        # Применяем размеры
        cover_height = int(cover_width * 1.5)
        self.cover_label.setFixedSize(cover_width, cover_height)

        # Обновляем шрифты
        self.title_label.setFont(QFont("Arial", title_font_size, QFont.Weight.Bold))
        self.description_label.setFont(QFont("Arial", desc_font_size))

        # Обновляем метаданные
        meta_widgets = [
            self.year_label, self.language_label, self.platform_label,
            self.size_label, self.rating_label, self.developer_label, self.genre_label
        ]
        for widget in meta_widgets:
            widget.setFont(QFont("Arial", meta_font_size))
            # Обновляем минимальную высоту для меток
            widget.setMinimumHeight(max(30, int(button_height * 0.6)))

        # Обновляем стиль панели метаданных
        meta_style = f"""
            QFrame {{
                background: rgba(30, 30, 30, 0.8);
                border-radius: 12px;
                padding: {meta_padding};
                margin: 10px 0;
            }}
        """
        # Находим панель метаданных и обновляем её стиль
        for i in range(self.layout().count()):
            main_card = self.layout().itemAt(i).widget()
            if isinstance(main_card, QFrame):
                for j in range(main_card.layout().count()):
                    content_layout = main_card.layout().itemAt(j)
                    if content_layout and hasattr(content_layout, 'count'):
                        for k in range(content_layout.count()):
                            widget = content_layout.itemAt(k).widget()
                            if isinstance(widget, QFrame) and hasattr(widget, 'layout'):
                                for m in range(widget.layout().count()):
                                    meta_panel = widget.layout().itemAt(m).widget()
                                    if isinstance(meta_panel, QFrame):
                                        meta_panel.setStyleSheet(meta_style)
                                        break

        # Обновляем отступы основного layout
        main_layout = self.layout()
        if main_layout:
            main_layout.setContentsMargins(*main_margins)

        # Обновляем размеры кнопок
        self.action_button.setMinimumSize(180, button_height)
        self.menu_button.setMinimumSize(70, button_height)
        self.back_button.setMinimumSize(140, button_height)

        # Обновляем обложку при изменении размера
        if hasattr(self, 'game_data') and self.game_data:
            self.update_cover_image()

    def _format_size(self, size_bytes):
        """Форматирует размер в читаемый формат"""
        if size_bytes >= 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
        elif size_bytes >= 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.0f} MB"
        else:
            return f"{size_bytes / 1024:.0f} KB"

    def update_installation_status(self, is_installed):
        """Обновить кнопки в зависимости от статуса установки"""
        self.is_installed = is_installed
        self.action_button.setText("ИГРАТЬ" if self.is_installed else "УСТАНОВИТЬ")
        self._update_action_button_style()

        # Показываем/скрываем кнопку меню
        self.menu_button.setVisible(self.is_installed)
        self.delete_action.setEnabled(self.is_installed)
        self.change_cover_action.setEnabled(self.is_installed)

    def update_cover_image(self):
        """Обновить изображение обложки"""
        logger.info(f"🖼️ Обновление обложки для игры: {self.game_data.get('title')}")

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
                logger.warning(f"⚠️ Обложка не найдена для игры: {self.game_data.get('title')}")
                self.cover_label.clear()
                return

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

        try:
            project_root = self.window().project_root
        except AttributeError:
            project_root = Path(".")

        # ИСПРАВЛЕНО: используем путь из настроек
        from core import get_users_subpath
        images_dir = Path(get_users_subpath("images")) / platform / game_id
        logger.info(f"🔍 Поиск обложки в: {images_dir}")

        try:
            images_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Директория для обложек создана/проверена: {images_dir}")
        except Exception as e:
            logger.error(f"❌ Ошибка создания директории для обложек: {e}")
            return None

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

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите новую обложку",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )

        if not file_path:
            logger.info("👤 Пользователь отменил выбор обложки")
            return

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

            try:
                project_root = self.window().project_root
            except AttributeError:
                project_root = Path(".")

            # ИСПРАВЛЕНО: используем путь из настроек
            from core import get_users_subpath
            cover_dir = Path(get_users_subpath("images")) / platform / game_id
            cover_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Создана директория для обложки: {cover_dir}")

            cover_filename = f"cover{file_ext}"
            destination_path = cover_dir / cover_filename

            for old_ext in valid_extensions:
                if old_ext != file_ext:
                    old_path = cover_dir / f"cover{old_ext}"
                    if old_path.exists():
                        old_path.unlink()
                        logger.info(f"🗑️ Удалена старая обложка: {old_path}")

            shutil.copy2(file_path, destination_path)
            logger.info(f"✅ Обложка сохранена: {destination_path}")

            self.update_cover_image()
            self._update_registry_with_cover_path(str(cover_dir))

            if self.change_cover_callback:
                self.change_cover_callback(self.game_data, str(destination_path))

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

            try:
                project_root = self.window().project_root
            except AttributeError:
                project_root = Path(".")

            # ИСПРАВЛЕНО: используем путь из настроек
            from core import get_users_path
            registry_path = Path(get_users_path()) / "installed_games.json"

            if not registry_path.exists():
                return

            with open(registry_path, 'r', encoding='utf-8') as f:
                registry = json.load(f)

            for game in registry.get('installed_games', []):
                if game.get('id') == game_id:
                    game['cover_directory'] = cover_dir_path
                    break

            with open(registry_path, 'w', encoding='utf-8') as f:
                json.dump(registry, f, ensure_ascii=False, indent=4)

            logger.info(f"✅ Реестр обновлен с путем к обложкам: {cover_dir_path}")

        except Exception as e:
            logger.error(f"❌ Ошибка обновления реестра: {e}")
            raise

    def _delete_game_files(self, game_data):
        """Удалить все файлы игры на основе данных из реестра"""
        try:
            try:
                project_root = self.window().project_root
            except AttributeError:
                project_root = Path(".")

            # ИСПРАВЛЕНО: используем пути из настроек
            from core import get_users_path, get_users_subpath
            registry_path = Path(get_users_path()) / "installed_games.json"

            if not registry_path.exists():
                logger.warning("⚠️ Реестр установленных игр не найден")
                return

            with open(registry_path, 'r', encoding='utf-8') as f:
                registry = json.load(f)

            game_id = game_data.get('id')
            game_info = registry.get(game_id)

            if not game_info:
                logger.warning(f"⚠️ Игра {game_id} не найдена в реестре")
                return

            paths_to_delete = [
                game_info.get('install_path'),
                game_info.get('launcher_path'),
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

            # ИСПРАВЛЕНО: используем путь из настроек для обложек
            cover_dir = Path(get_users_subpath("images")) / game_info.get('platform') / game_id
            if cover_dir.exists() and cover_dir.is_dir():
                shutil.rmtree(cover_dir)
                logger.info(f"🗑️ Удалена папка с обложками: {cover_dir}")

            # ИСПРАВЛЕНО: используем путь из настроек для лаунчеров
            launcher_path = Path(get_users_subpath("launchers")) / f"{game_id}.sh"
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

            try:
                project_root = self.window().project_root
            except AttributeError:
                project_root = Path(".")

            # ИСПРАВЛЕНО: используем путь из настроек
            from core import get_users_path
            registry_path = Path(get_users_path()) / "installed_games.json"

            if not registry_path.exists():
                return

            with open(registry_path, 'r', encoding='utf-8') as f:
                registry = json.load(f)

            if game_id in registry:
                del registry[game_id]
                logger.info(f"✅ Игра удалена из реестра: {game_id}")

                if len(registry) == 1 and "installed_games" in registry and not registry["installed_games"]:
                    os.remove(registry_path)
                    logger.info("🗑️ Удален файл реестра (последняя игра)")
                else:
                    with open(registry_path, 'w', encoding='utf-8') as f:
                        json.dump(registry, f, ensure_ascii=False, indent=4)

        except Exception as e:
            logger.error(f"❌ Ошибка удаления из реестра: {e}")
            raise

    def load_game(self, game_data):
        """Загружает данные игры и отображает их на странице"""
        if not game_data:
            return

        try:
            game_id = game_data.get('id')
            if game_id:
                from app.modules.module_logic.game_data_manager import get_game_data_manager
                manager = get_game_data_manager()

                if manager:
                    actual_game_data = manager.get_game_by_id(game_id)
                    if actual_game_data:
                        game_data = actual_game_data

            # Проверка установки через installed_games.json
            installed_games_file = Path(get_users_path()) / 'installed_games.json'
            is_installed_status = False

            if installed_games_file.exists():
                with open(installed_games_file, 'r', encoding='utf-8') as f:
                    installed_games = json.load(f)
                    is_installed_status = game_id in installed_games

            self.set_game(game_data, is_installed_status)

        except Exception as e:
            logger.error(f"Ошибка загрузки данных игры: {e}")
            # Fallback
            self.set_game(game_data, game_data.get('is_installed', False))

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
                self._delete_game_files(self.game_data)
                self._remove_from_registry(self.game_data)
                self.is_installed = False
                self.update_installation_status(False)
                self.cover_label.clear()

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
