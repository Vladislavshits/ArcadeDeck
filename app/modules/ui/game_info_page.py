import os
import shutil
import logging
import json

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QMenu, QToolButton, QMessageBox, QFileDialog, QFrame,
    QApplication, QSizePolicy, QScrollArea
)
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPoint, QSize, QTimer
from pathlib import Path

# Импорт пути игровых данных
from core import get_users_path

# Импорт модуля навигации
from navigation import NavigationLayer

from app.modules.module_logic.game_art_manager import GameArtManager

from app.modules.ui.message_dialog import show_info, show_error, show_warning, show_question

logger = logging.getLogger('Экран "Об игре"')


class GameInfoPage(QWidget):
    coverUpdated = pyqtSignal(str)
    """Страница информации об игре"""
    def __init__(self, game_data=None, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self.is_installed = False

        # Установка коллбеков
        self._back_callback = None
        self._action_callback = None
        self._delete_callback = None
        self._change_cover_callback = None
        self.meta_panel = None

        # Эти лейблы хранят значения, без префиксов и иконок
        self.year_label = QLabel("—")
        self.language_label = QLabel("—")
        self.platform_label = QLabel("—")
        self.size_label = QLabel("—")
        self.rating_label = QLabel("—")
        self.developer_label = QLabel("—")
        self.fps_label = QLabel("—")
        self.genre_label = QLabel("—")

        self.meta_tiles_row1 = []  # Плитки для первой строки
        self.meta_tiles_row2 = []  # Плитки для второй строки

        # Настройки размеров плиток метаданных (удобный блок для кастомизации)
        # Эти значения будут адаптироваться в _adapt_to_screen_size
        # Вы можете изменить базовые значения здесь для глобальной настройки
        self.meta_tile_width = 150  # Базовая ширина плитки для первого ряда
        self.meta_tile_width_row2 = 250  # БОЛЬШАЯ ширина для второго ряда с длинным текстом
        self.meta_tile_height = 80  # Базовая высота плитки
        self.meta_tile_spacing = 15  # Расстояние между плитками
        self.meta_container_margins = (10, 10, 10, 10)  # Отступы контейнера (left, top, right, bottom)
        self.meta_value_font_size = 16  # Базовый размер шрифта для значения (жирный)
        self.meta_label_font_size = 12  # Базовый размер шрифта для лейбла (нормальный)
        self.meta_tile_border_radius = 12  # Радиус скругления плиток

        self._init_ui()

        # Настройка начальной навигации
        self._refresh_navigation_widgets()

        if game_data:
            self.set_game(game_data, is_installed=False)

    def _init_ui(self):
        """Initialize PS5 style minimalistic UI"""

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 30, 40, 30)
        main_layout.setSpacing(0)

        # Главная карточка
        main_card = QFrame()

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

        # Обложка игры
        self.cover_label = QLabel()
        self.cover_label.setMinimumSize(300, 450)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_layout.addWidget(self.cover_label)

        return cover_widget

    def _create_info_section(self):
        """Создает правую секцию с информацией и кнопками"""
        info_widget = QFrame()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(25)

        # Название игры
        self.title_label = QLabel("Grand Theft Auto: San Andreas")
        self.title_label.setFont(QFont("Arial", 32, QFont.Weight.Bold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.title_label.setWordWrap(True)
        info_layout.addWidget(self.title_label)

        # Описание игры
        self.description_label = QLabel("Загрузка описания...")
        self.description_label.setWordWrap(True)
        self.description_label.setFont(QFont("Arial", 16))
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.description_label.setMinimumHeight(150)
        info_layout.addWidget(self.description_label)

        # Два горизонтальных скроллера с плитками метаданных
        meta_scroll_area1 = self._create_meta_scroll_area(row=1)
        info_layout.addWidget(meta_scroll_area1)
        
        meta_scroll_area2 = self._create_meta_scroll_area(row=2)
        info_layout.addWidget(meta_scroll_area2)

        info_layout.addStretch()

        # Панель кнопок
        button_panel = self._create_button_panel()
        info_layout.addWidget(button_panel)

        self.menu_panel = self._create_game_menu_panel()

        return info_widget

    def _create_meta_scroll_area(self, row=1):
        """Создает горизонтальный скроллер для плиток метаданных"""
        scroll_area = QScrollArea()
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFixedHeight(100)  # Фиксированная высота для скроллера
        
        # Контейнер для плиток
        container = QWidget()
        
        if row == 1:
            self.meta_layout_row1 = QHBoxLayout(container)
            self.meta_layout_row1.setSpacing(self.meta_tile_spacing)
            self.meta_layout_row1.setContentsMargins(*self.meta_container_margins)
            self.meta_layout_row1.setAlignment(Qt.AlignmentFlag.AlignLeft)
        else:
            self.meta_layout_row2 = QHBoxLayout(container)
            self.meta_layout_row2.setSpacing(self.meta_tile_spacing)
            self.meta_layout_row2.setContentsMargins(*self.meta_container_margins)
            self.meta_layout_row2.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        scroll_area.setWidget(container)
        scroll_area.setWidgetResizable(True)
        
        return scroll_area

    def _create_meta_panels(self):
        """Создает две строки плиток метаданных в горизонтальных скроллерах"""
        
        # Очищаем старые плитки
        for tile in self.meta_tiles_row1:
            tile.deleteLater()
        for tile in self.meta_tiles_row2:
            tile.deleteLater()
            
        self.meta_tiles_row1.clear()
        self.meta_tiles_row2.clear()

        # Первая строка: основные метаданные
        meta_items_row1 = [
            ("FPS", self.fps_label),
            ("Платформа", self.platform_label),
            ("Размер", self.size_label),
            ("Год", self.year_label),
            ("Рейтинг", self.rating_label),
        ]

        # Вторая строка: дополнительные метаданные (с увеличенной шириной)
        meta_items_row2 = [
            ("Язык", self.language_label),
            ("Разработчик", self.developer_label),
            ("Жанр", self.genre_label),
        ]

        # Создаем плитки для первой строки
        for label_text, value_label in meta_items_row1:
            tile = self._create_meta_tile(label_text, value_label, row=1)
            self.meta_layout_row1.addWidget(tile)
            self.meta_tiles_row1.append(tile)

        # Создаем плитки для второй строки (с увеличенной шириной)
        for label_text, value_label in meta_items_row2:
            tile = self._create_meta_tile(label_text, value_label, row=2)
            self.meta_layout_row2.addWidget(tile)
            self.meta_tiles_row2.append(tile)

    def _create_meta_tile(self, label_text, value_label, row=1):
        """Создает одну плитку метаданных"""
        # Выбираем ширину в зависимости от ряда
        if row == 1:
            tile_width = self.meta_tile_width
        else:
            tile_width = self.meta_tile_width_row2
            
        tile = QFrame()
        tile.setObjectName("MetaTile")
        tile.setProperty("class", f"{self.window().property('class')}")
        tile.setFixedSize(tile_width, self.meta_tile_height)

        tile_layout = QVBoxLayout(tile)
        tile_layout.setContentsMargins(12, 10, 12, 10)
        tile_layout.setSpacing(5)

        # Значение
        value_label.setObjectName("meta_value")
        value_label.setFont(QFont("Arial", self.meta_value_font_size, QFont.Weight.Bold))
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setWordWrap(True)
        
        # Для второго ряда уменьшаем шрифт если текст слишком длинный
        if row == 2:
            text = value_label.text()
            if len(text) > 15:  # Если текст длиннее 15 символов
                value_label.setFont(QFont("Arial", self.meta_value_font_size - 2, QFont.Weight.Bold))

        # Лейбл
        label_label = QLabel(label_text)
        label_label.setObjectName("meta_label")
        label_label.setFont(QFont("Arial", self.meta_label_font_size))
        label_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_label.setWordWrap(True)

        tile_layout.addWidget(value_label)
        tile_layout.addWidget(label_label)

        return tile

    def _create_button_panel(self):
        """Создает панель кнопок"""
        button_panel = QFrame()
        button_panel.setStyleSheet("QFrame { background: transparent; }")

        button_layout = QHBoxLayout(button_panel)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Основная кнопка действия
        self.action_button = QPushButton("ИГРАТЬ")
        self.action_button.setMinimumSize(180, 60)
        self.action_button.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.action_button.setProperty("focused", False)

        self.menu_button = QPushButton("⚙")
        self.menu_button.setFixedSize(80, 60)
        self.menu_button.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.menu_button.pressed.connect(
            self.open_menu_from_gamepad
        )

        # Кнопка назад
        self.back_button = QPushButton("НАЗАД")
        self.back_button.setMinimumSize(140, 60)
        self.back_button.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.back_button.setProperty("focused", False)

        button_layout.addWidget(self.action_button)
        button_layout.addWidget(self.menu_button)
        button_layout.addWidget(self.back_button)

        self.action_button.clicked.connect(self.on_action)
        self.back_button.clicked.connect(self.on_back)

        return button_panel

    def open_menu_from_gamepad(self):
        self.menu_button.clearFocus()

        QApplication.processEvents()

        self.show_menu_dialog()

    def _create_game_menu_panel(self):
        """Контекстное меню игры через QDialog"""

        dialog = QDialog(self)
        dialog.setObjectName("GameMenuDialog")
        dialog.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        dialog.setModal(True)

        # Без системного title bar
        dialog.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog
        )

        dialog.setFixedSize(500, 320)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # --- Кнопки ---
        self.btn_add_to_steam = QPushButton("🎮 Добавить в Steam")
        self.btn_change_cover = QPushButton("🎨 Изменить обложку")
        self.btn_delete_game = QPushButton("🗑️ Удалить игру")
        self.btn_close_menu = QPushButton("❌ Закрыть")

        self.menu_buttons = [
            self.btn_add_to_steam,
            self.btn_change_cover,
            self.btn_delete_game,
            self.btn_close_menu
        ]

        for btn in self.menu_buttons:
            btn.setMinimumHeight(52)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            layout.addWidget(btn)

        # --- Signals ---
        self.btn_add_to_steam.clicked.connect(self.on_add_to_steam)
        self.btn_change_cover.clicked.connect(self.on_change_cover)
        self.btn_delete_game.clicked.connect(self.on_delete)

        self.btn_close_menu.clicked.connect(dialog.close)

        dialog.finished.connect(self.on_menu_closed)

        return dialog

    def show_menu_dialog(self):
        """Показывает диалоговое меню"""

        if hasattr(self.window(), 'navigation_controller'):
            nav = self.window().navigation_controller

            nav.register_widgets(
                NavigationLayer.DIALOG,
                self.menu_buttons
            )

            nav.switch_layer(NavigationLayer.DIALOG)

        # ВАЖНО: сначала показать окно
        self.menu_panel.show()

        # Активируем окно
        self.menu_panel.activateWindow()
        self.menu_panel.raise_()

        # Даём Qt обработать show()
        QApplication.processEvents()

        # Ставим фокус
        self.btn_add_to_steam.setFocus(
            Qt.FocusReason.OtherFocusReason
        )

        # Запускаем modal loop
        self.menu_panel.open()

    def on_menu_closed(self):
        """Восстановление навигации после закрытия меню"""

        logger.info("📋 Меню закрыто")

        if hasattr(self.window(), 'navigation_controller'):
            nav = self.window().navigation_controller

            nav.switch_layer(NavigationLayer.GAME_INFO)

            QTimer.singleShot(
                0,
                lambda: nav.set_focus(
                    NavigationLayer.GAME_INFO,
                    1 if self.is_installed else 0
                )
            )

    def on_add_to_steam(self):
        """Handle add to Steam action from menu"""
        if not self.game_data:
            logger.warning("⚠️ Попытка добавить в Steam без данных игры")
            return

        # Закрываем меню
        if hasattr(self, 'menu_panel') and self.menu_panel.isVisible():
            self.menu_panel.close()

        nav = self.window().navigation_controller if hasattr(self.window(), 'navigation_controller') else None

        try:
            from app.modules.module_logic.add_to_steam import add_game_to_steam

            # Получаем project_root из родительского окна
            try:
                project_root = self.window().project_root
            except AttributeError:
                project_root = Path(".")

            # Вызываем функцию добавления в Steam
            success = add_game_to_steam(self.game_data, project_root)

            if success:
                show_info(
                    self,
                    "Успех! 🎉",
                    f"Игра '{self.game_data.get('title', '')}' успешно добавлена в Steam!\n\n"
                    "Перезагрузите Steam для отображения игры.",
                    nav_controller=nav
                )
            else:
                show_warning(
                    self,
                    "Ошибка",
                    "Не удалось добавить игру в Steam.\n\n"
                    "Убедитесь, что:\n"
                    "• Команда 'steamos-add-to-steam' доступа\n"
                    "• Игра установлена\n"
                    "• Проверьте логи для подробностей",
                    nav_controller=nav
                )

        except Exception as e:
            logger.error(f"❌ Ошибка при добавлении в Steam: {e}")
            show_error(
                self,
                "Ошибка",
                f"Произошла непредвиденная ошибка:\n{str(e)}",
                nav_controller=nav
            )

    def set_game(self, game_data: dict, is_installed: bool):
        """Установка данных игры + ОБЛОЖКА"""
        self.game_data = game_data
        self.is_installed = is_installed

        # Заполняем текст
        self.title_label.setText(game_data.get('title', 'Без названия'))
        self.description_label.setText(game_data.get('description', 'Описание недоступно'))
        
        # Метаданные
        self.year_label.setText(game_data.get('year', '—'))
        self.language_label.setText(game_data.get('language', '—'))
        self.platform_label.setText(game_data.get('platform', '—'))
        self.size_label.setText(self._format_size(game_data.get('size_bytes', 0)))
        self.rating_label.setText(game_data.get('rating', '—'))
        self.developer_label.setText(game_data.get('developer', '—'))
        self.genre_label.setText(game_data.get('genre', '—'))
        self.fps_label.setText(game_data.get('fps', '—'))  # или 'fps_limit', 'target_fps' — как будет в JSON

        # Создаем плитки метаданных
        self._create_meta_panels()

        # Загружаем обложку после полного построения UI
        QTimer.singleShot(0, lambda: self._load_cover(game_data))

        # Кнопка действия - обновляем
        self.update_installation_status(is_installed)

    def _load_cover(self, game_data: dict):
        """Единая функция загрузки обложки — вызывается при set_game и после смены обложки"""
        try:
            project_root = self.window().project_root
        except AttributeError:
            project_root = Path(".")

        art_manager = GameArtManager(project_root)
        pixmap = art_manager.refresh_game_cover_optimized(
            game_data,
            container_size=(300, 450)  # размер cover_label
        )

        if pixmap:
            self.cover_label.setPixmap(pixmap)
            logger.info(f"Обложка успешно отображена на экране 'Об игре'")
        else:
            # Плейсхолдер
            placeholder = QPixmap(300, 450)
            placeholder.fill(Qt.GlobalColor.darkGray)
            self.cover_label.setPixmap(placeholder)
            logger.info(f"Установлен плейсхолдер (обложка не найдена)")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adapt_to_screen_size()

    def _adapt_to_screen_size(self):
        """Адаптирует интерфейс к размеру экрана"""
        screen_width = self.width()

        # Адаптация плиток метаданных и экрана
        if screen_width < 1280:
            # Маленький экран (Steam Deck портретный режим)
            cover_width = 280
            title_font_size = 24
            desc_font_size = 14
            meta_font_size = 11  # Уменьшен для Steam Deck
            button_height = 50
            main_margins = (20, 20, 20, 20)
            self.meta_tile_width = 120
            self.meta_tile_width_row2 = 205  # Увеличенная ширина для второго ряда
            self.meta_tile_height = 70
            self.meta_tile_spacing = 10
            self.meta_container_margins = (5, 5, 5, 5)
            self.meta_value_font_size = 14
            self.meta_label_font_size = 10
            self.meta_tile_border_radius = 8
            meta_padding = "10px"  # Меньше padding для маленьких экранов
        elif screen_width < 1920:
            # Средний экран
            cover_width = 350
            title_font_size = 28
            desc_font_size = 15
            meta_font_size = 12
            button_height = 55
            main_margins = (30, 25, 30, 25)
            self.meta_tile_width = 140
            self.meta_tile_width_row2 = 170  # Увеличенная ширина для второго ряда
            self.meta_tile_height = 75
            self.meta_tile_spacing = 12
            self.meta_container_margins = (8, 8, 8, 8)
            self.meta_value_font_size = 15
            self.meta_label_font_size = 11
            self.meta_tile_border_radius = 10
            meta_padding = "12px"
        else:
            # Большой экран
            cover_width = 400
            title_font_size = 32
            desc_font_size = 16
            meta_font_size = 13
            button_height = 60
            main_margins = (40, 30, 40, 30)
            self.meta_tile_width = 160
            self.meta_tile_width_row2 = 200  # Увеличенная ширина для второго ряда
            self.meta_tile_height = 80
            self.meta_tile_spacing = 15
            self.meta_container_margins = (10, 10, 10, 10)
            self.meta_value_font_size = 16
            self.meta_label_font_size = 12
            self.meta_tile_border_radius = 12
            meta_padding = "15px"

        # Применяем размеры
        cover_height = int(cover_width * 1.5)
        self.cover_label.setFixedSize(cover_width, cover_height)

        # Обновляем шрифты
        self.title_label.setFont(QFont("Arial", title_font_size, QFont.Weight.Bold))
        self.description_label.setFont(QFont("Arial", desc_font_size))

        # Обновляем отступы основного layout
        main_layout = self.layout()
        if main_layout:
            main_layout.setContentsMargins(*main_margins)

        # Обновляем панель метаданных
        self._update_meta_panel_safe()

        # Обновляем размеры кнопок
        self.action_button.setMinimumSize(180, button_height)
        self.menu_button.setMinimumSize(70, button_height)
        self.back_button.setMinimumSize(140, button_height)

        # Обновляем обложку при изменении размера
        if hasattr(self, 'game_data') and self.game_data:
            self.update_cover_image()

    def _update_meta_panel_safe(self):
        """Безопасное обновление панели метаданных"""
        try:
            # Обновляем размеры и стили всех плиток первого ряда
            for tile in self.meta_tiles_row1:
                if hasattr(tile, 'setFixedSize'):
                    tile.setFixedSize(self.meta_tile_width, self.meta_tile_height)
                    
                    # Обновляем шрифты внутри плитки
                    layout = tile.layout()
                    if layout and layout.count() >= 2:
                        value_label = layout.itemAt(0).widget()
                        label_label = layout.itemAt(1).widget()
                        if isinstance(value_label, QLabel):
                            value_label.setFont(QFont("Arial", self.meta_value_font_size, QFont.Weight.Bold))
                        if isinstance(label_label, QLabel):
                            label_label.setFont(QFont("Arial", self.meta_label_font_size))

            # Обновляем размеры и стили всех плиток второго ряда
            for tile in self.meta_tiles_row2:
                if hasattr(tile, 'setFixedSize'):
                    tile.setFixedSize(self.meta_tile_width_row2, self.meta_tile_height)

                    # Обновляем шрифты внутри плитки
                    layout = tile.layout()
                    if layout and layout.count() >= 2:
                        value_label = layout.itemAt(0).widget()
                        label_label = layout.itemAt(1).widget()
                        if isinstance(value_label, QLabel):
                            # Для длинного текста уменьшаем шрифт
                            text = value_label.text()
                            if len(text) > 15:
                                value_label.setFont(QFont("Arial", self.meta_value_font_size - 2, QFont.Weight.Bold))
                            else:
                                value_label.setFont(QFont("Arial", self.meta_value_font_size, QFont.Weight.Bold))
                        if isinstance(label_label, QLabel):
                            label_label.setFont(QFont("Arial", self.meta_label_font_size))

            # Обновляем spacing и margins для layout'ов
            if hasattr(self, 'meta_layout_row1'):
                self.meta_layout_row1.setSpacing(self.meta_tile_spacing)
                self.meta_layout_row1.setContentsMargins(*self.meta_container_margins)
            if hasattr(self, 'meta_layout_row2'):
                self.meta_layout_row2.setSpacing(self.meta_tile_spacing)
                self.meta_layout_row2.setContentsMargins(*self.meta_container_margins)

            logger.info("Meta panels updated successfully")
        except Exception as e:
            logger.error(f"Error updating meta panels: {e}")

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
        old_installed = self.is_installed
        self.is_installed = is_installed

        # Сохраняем текущий фокус ДО изменений
        current_focus_widget = QApplication.focusWidget()

        self.action_button.setText("ИГРАТЬ" if self.is_installed else "УСТАНОВИТЬ")

        # Показываем/скрываем кнопку меню
        self.menu_button.setVisible(self.is_installed)

        self.btn_delete_game.setEnabled(self.is_installed)
        self.btn_change_cover.setEnabled(self.is_installed)
        self.btn_add_to_steam.setEnabled(self.is_installed)

        # === КРИТИЧНО ВАЖНО ===
        self._refresh_navigation_widgets()

        # Восстанавливаем фокус ТОЛЬКО если он был на наших кнопках
        if (current_focus_widget and
            current_focus_widget in [self.action_button, self.menu_button, self.back_button]):
            QTimer.singleShot(10, lambda: current_focus_widget.setFocus(Qt.FocusReason.OtherFocusReason))

    def _refresh_navigation_widgets(self):
        """Обновить список виджетов для навигации"""
        if hasattr(self, 'window') and hasattr(self.window(), 'navigation_controller'):
            nav = self.window().navigation_controller
            
            # Собираем актуальный список виджетов
            widgets = [self.action_button, self.back_button]

            if self.is_installed:
                widgets.insert(1, self.menu_button)
            
            # Регистрируем обновленный список
            nav.register_widgets(NavigationLayer.GAME_INFO, widgets)
            
            # Устанавливаем фокус на первую кнопку
            if self.isVisible():
                nav.set_focus(NavigationLayer.GAME_INFO, 0)

    def update_cover_image(self):
        """Обновить изображение обложки через GameArtManager с единым масштабированием"""
        logger.info(f"🖼️ Обновление обложки для игры: {self.game_data.get('title')}")

        cover_pixmap = None
        
        # Получаем обложку исключительно через GameArtManager
        if hasattr(self, 'window') and hasattr(self.window(), 'game_data_manager'):
            manager = self.window().game_data_manager
            if manager and hasattr(manager, 'art_manager'):
                cover_pixmap = manager.art_manager.refresh_game_cover(
                    self.game_data, 
                    (self.cover_label.width(), self.cover_label.height())
                )
        
        # Устанавливаем обложку с единым масштабированием
        if cover_pixmap and not cover_pixmap.isNull():
            # Масштабирование: KeepAspectRatioByExpanding + центрирование
            scaled_pixmap = cover_pixmap.scaled(
                self.cover_label.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Создаем прозрачный QPixmap для центрирования
            final_pixmap = QPixmap(self.cover_label.size())
            final_pixmap.fill(Qt.GlobalColor.transparent)
            
            # Вычисляем позицию для центрирования
            x = (final_pixmap.width() - scaled_pixmap.width()) // 2
            y = (final_pixmap.height() - scaled_pixmap.height()) // 2
            
            # Рисуем центрированное изображение
            from PyQt6.QtGui import QPainter
            painter = QPainter(final_pixmap)
            painter.drawPixmap(x, y, scaled_pixmap)
            painter.end()
            
            self.cover_label.setPixmap(final_pixmap)
            logger.info("✅ Обложка успешно обновлена через GameArtManager")
        else:
            # Очищаем лейбл если обложка не найдена
            self.cover_label.clear()
            logger.warning("⚠️ Обложка не найдена через GameArtManager")

    def get_custom_cover_path(self):
        """Получить путь к пользовательской обложке игры через GameArtManager"""
        if not self.game_data:
            logger.warning("⚠️ Нет данных игры для поиска обложки")
            return None

        # Используем GameArtManager для получения пути к обложке
        if hasattr(self, 'window') and hasattr(self.window(), 'game_data_manager'):
            manager = self.window().game_data_manager
            if manager and hasattr(manager, 'art_manager'):
                platform = self.game_data.get('platform')
                title = self.game_data.get('title')
                
                if platform and title:
                    cover_path = manager.art_manager.get_cover_path(platform, title)
                    if cover_path:
                        logger.info(f"✅ Обложка найдена через GameArtManager: {cover_path}")
                        return cover_path
        
        logger.info("📭 Обложка не найдена через GameArtManager")
        return None

    def on_change_cover(self):
        """Handle change cover action from menu"""
        if not self.game_data:
            logger.warning("⚠️ Попытка изменить обложку без данных игры")
            return
        # Закрываем меню, чтобы не было конфликта слоёв
        if hasattr(self, 'menu_panel') and self.menu_panel.isVisible():
            self.menu_panel.close()

        logger.info(f"🎨 Запрос на изменение обложки для игры: {self.game_data.get('title')}")

        # Определяем nav один раз в начале
        nav = self.window().navigation_controller if hasattr(self.window(), 'navigation_controller') else None
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
            show_warning(
                self,
                "Неверный формат",
                f"Пожалуйста, выберите изображение в одном из форматов: {', '.join(valid_extensions)}",
                nav_controller=nav
            )
            return

        try:
            game_id = self.game_data.get('id')
            platform = self.game_data.get('platform')

            if not game_id or not platform:
                logger.error("❌ Не удалось определить ID игры или платформу")
                show_warning(self, "Ошибка", "Не удалось определить ID игры или платформу", nav_controller=nav)
                return

            try:
                project_root = self.window().project_root
            except AttributeError:
                project_root = Path(".")

            # Используем путь из настроек
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

            show_info(self, "Успех! 🎉", f"Обложка успешно обновлена!\n\nФайл: {cover_filename}\nПуть: {cover_dir}", nav_controller=nav)
            logger.info(f"✅ Обложка успешно изменена и уведомление показано")

        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении обложки: {e}")
            show_error(self, "Ошибка", f"Не удалось сохранить обложку:\n{str(e)}", nav_controller=nav)

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
            if hasattr(self, 'window') and hasattr(self.window(), 'navigation_controller'):
                nav = self.window().navigation_controller
                nav.switch_layer(NavigationLayer.MAIN)  # Переключаем слой, как при B
                logger.info("📚 Возврат из информации об игре в библиотеку по кнопке 'Назад'")
            if self.back_callback:
                self.back_callback()  # Вызываем show_library или аналог

    def on_action(self):
        """Обработка кнопки действия (Установить/Играть)"""
        if not self.game_data:
            return
            
        if self.is_installed:
            # Запуск игры
            self._launch_installed_game()
        else:
            # Установка игры
            self._show_standard_installation()

    def _show_standard_installation(self):
        logger.info(f"🎮 Начинаем установку: {self.game_data.get('title')}")
        try:
            parent_window = self.window()
            if not hasattr(parent_window, 'project_root'):
                logger.error("❌ Не найден project_root")
                if self.action_callback:
                    self.action_callback(self.game_data, self.is_installed)
                return

            from app.modules.installer.install import InstallDialog

            self._install_dialog = InstallDialog(  # <-- сохраняем как атрибут
                game_data=self.game_data,
                project_root=parent_window.project_root,
                parent=parent_window
            )
            self._install_dialog.installation_finished.connect(
                lambda: self.update_installation_status(True)
            )

        except Exception as e:
            logger.error(f"❌ Ошибка показа диалога установки: {e}")
            if self.action_callback:
                self.action_callback(self.game_data, self.is_installed)

    def _launch_installed_game(self):
        """Запуск установленной игры"""
        if self.action_callback:
            self.action_callback(self.game_data, self.is_installed)

    def on_delete(self):
        if not self.game_data:
            return

        # Закрываем меню
        if hasattr(self, 'menu_panel') and self.menu_panel.isVisible():
            self.menu_panel.close()

        game_title = self.game_data.get("title", "эту игру")
        nav = self.window().navigation_controller if hasattr(self.window(), 'navigation_controller') else None

        # Даём время меню закрыться
        QTimer.singleShot(100, lambda: self._confirm_delete(game_title, nav))

    def _confirm_delete(self, game_title, nav):
        if show_question(
            self,
            "Подтверждение удаления",
            f"Вы уверены, что хотите удалить '{game_title}'?\n\n"
            "Будут удалены:\n"
            "• Файл игры\n"
            "• Скрипт запуска\n"
            "• Папка с обложками\n"
            "• Запись в реестре",
            nav_controller=nav
        ):
            try:
                self._delete_game_files(self.game_data)
                self._remove_from_registry(self.game_data)
                self.is_installed = False
                self.update_installation_status(False)
                self.cover_label.clear()

                if self.delete_callback:
                    self.delete_callback(self.game_data)

                show_info(self, "Успех", f"Игра '{game_title}' успешно удалена!", nav_controller=nav)

            except Exception as e:
                logger.error(f"❌ Ошибка при удалении игры: {e}")
                show_error(self, "Ошибка", f"Не удалось полностью удалить игру:\n{str(e)}", nav_controller=nav)

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
