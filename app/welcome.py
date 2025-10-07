import os
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QLabel, QVBoxLayout, QPushButton,
    QHBoxLayout, QButtonGroup, QFrame, QApplication, QFileDialog
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from settings import app_settings
from app.ui_assets.theme_manager import theme_manager
from core import THEME_FILE


class PathSelectionPage(QWizardPage):
    """Страница выбора пути установки в мастере приветствия"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Расположение данных")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        title = QLabel("Выберите расположение для игр и данных")
        title.setFont(QFont("Arial", 20))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Виджет выбора пути в одном ряду
        path_frame = QFrame()
        path_frame.setObjectName("PathSelectionFrame")
        path_layout = QHBoxLayout(path_frame)  # Меняем на QHBoxLayout
        path_layout.setContentsMargins(20, 20, 20, 20)
        path_layout.setSpacing(10)

        # Кнопки выбора в одном ряду
        self.default_btn = QPushButton("По умолчанию")
        self.default_btn.setCheckable(True)
        self.default_btn.setFixedHeight(60)
        self.default_btn.setFixedWidth(180)  # Фиксированная ширина
        self.default_btn.clicked.connect(self.select_default)

        self.sd_card_btn = QPushButton("SD-карта")
        self.sd_card_btn.setCheckable(True)
        self.sd_card_btn.setFixedHeight(60)
        self.sd_card_btn.setFixedWidth(180)  # Фиксированная ширина
        self.sd_card_btn.clicked.connect(self.select_sd_card)

        self.custom_btn = QPushButton("Выбрать вручную")
        self.custom_btn.setCheckable(True)
        self.custom_btn.setFixedHeight(60)
        self.custom_btn.setFixedWidth(180)  # Фиксированная ширина
        self.custom_btn.clicked.connect(self.select_custom)

        path_layout.addWidget(self.default_btn)
        path_layout.addWidget(self.sd_card_btn)
        path_layout.addWidget(self.custom_btn)

        # Центрируем кнопки
        path_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(path_frame)

        # Метка текущего выбора
        self.path_label = QLabel()
        self.path_label.setWordWrap(True)
        self.path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.path_label.setFont(QFont("Arial", 12))
        layout.addWidget(self.path_label)

        # Информация
        info = QLabel(
            "Выберите где будут храниться игры, обложки и другие данные. "
            "Вы всегда сможете изменить это в настройках."
        )
        info.setWordWrap(True)
        info.setFont(QFont("Arial", 12))
        layout.addWidget(info)

        self.setLayout(layout)

        # Устанавливаем выбор по умолчанию
        self.select_default()

    def get_default_path(self):
        """Путь по умолчанию (в директории программы)"""
        return Path(__file__).parent.parent / "users"

    def get_sd_card_path(self):
        """Путь к SD-карте на Steam Deck"""
        # Стандартные пути к SD-карте на Steam Deck
        possible_paths = [
            "/run/media/mmcblk0p1",
            "/run/media/mmcblk1p1",
            "/media/sdcard",
            "/mnt/sdcard"
        ]

        for path in possible_paths:
            if os.path.exists(path):
                sd_path = Path(path) / "ArcadeDeck" / "users"
                sd_path.mkdir(parents=True, exist_ok=True)
                return sd_path

        # Если SD-карта не найдена, создаем в домашней директории
        home_path = Path.home() / "ArcadeDeck" / "users"
        home_path.mkdir(parents=True, exist_ok=True)
        return home_path

    def select_default(self):
        """Выбор пути по умолчанию"""
        path = self.get_default_path()
        self.update_selection(path, "default")

    def select_sd_card(self):
        """Выбор пути на SD-карте"""
        path = self.get_sd_card_path()
        self.update_selection(path, "sd_card")

    def select_custom(self):
        """Выбор пользовательского пути"""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)

        if dialog.exec() == QFileDialog.DialogCode.Accepted:
            selected = dialog.selectedFiles()[0]
            path = Path(selected) / "ArcadeDeck" / "users"
            path.mkdir(parents=True, exist_ok=True)
            self.update_selection(path, "custom")

    def update_selection(self, path, path_type):
        """Обновляет интерфейс и сохраняет настройки"""
        self.default_btn.setChecked(path_type == "default")
        self.sd_card_btn.setChecked(path_type == "sd_card")
        self.custom_btn.setChecked(path_type == "custom")
        self.path_label.setText(f"Будет использоваться: {path}")

        # Сохраняем настройки
        app_settings.set_users_path(str(path))
        app_settings.set_users_path_type(path_type)


class WelcomeWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добро пожаловать в ArcadeDeck!")
        self.showMaximized()

        # Тексты кнопок мастера
        self.setButtonText(QWizard.WizardButton.BackButton, "Назад")
        self.setButtonText(QWizard.WizardButton.NextButton, "Далее")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Готово")

        # Отключаем отмену и пропуск
        self.setOption(QWizard.WizardOption.NoCancelButton)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage)

        # Страница 1: Приветствие
        self.page1 = QWizardPage()
        self.page1.setTitle("Добро пожаловать")
        layout1 = QVBoxLayout()
        title = QLabel("ArcadeDeck")
        title.setFont(QFont("Arial", 48, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout1.addWidget(title)

        desc = QLabel("Ваш помощник в настройке игр для Steam Deck")
        desc.setFont(QFont("Arial", 24))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout1.addWidget(desc)

        self.page1.setLayout(layout1)
        self.addPage(self.page1)

        # Страница 2: Выбор темы
        self.page2 = QWizardPage()
        self.page2.setTitle("Выбор темы")
        layout2 = QVBoxLayout()

        theme_label = QLabel("Выберите предпочитаемую цветовую схему:")
        theme_label.setFont(QFont("Arial", 20))
        theme_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout2.addWidget(theme_label)

        self.theme_group = QButtonGroup()

        # Кнопки-плитки выбора темы
        self.dark_theme_btn = QPushButton("Темная тема")
        self.dark_theme_btn.setObjectName("themeButton")
        self.dark_theme_btn.setCheckable(True)
        self.dark_theme_btn.setFixedSize(300, 200)
        self.dark_theme_btn.setFont(QFont("Arial", 18))

        self.light_theme_btn = QPushButton("Светлая тема")
        self.light_theme_btn.setObjectName("themeButton")
        self.light_theme_btn.setCheckable(True)
        self.light_theme_btn.setFixedSize(300, 200)
        self.light_theme_btn.setFont(QFont("Arial", 18))

        self.theme_group.addButton(self.dark_theme_btn, 0)
        self.theme_group.addButton(self.light_theme_btn, 1)
        self.dark_theme_btn.setChecked(True)

        buttons_frame = QFrame()
        buttons_frame.setObjectName("ThemeButtonsFrame")
        buttons_frame.setFrameShape(QFrame.Shape.StyledPanel)
        buttons_frame.setLineWidth(2)
        buttons_layout = QHBoxLayout(buttons_frame)
        buttons_layout.addWidget(self.dark_theme_btn)
        buttons_layout.addWidget(self.light_theme_btn)
        layout2.addWidget(buttons_frame)
        layout2.addStretch()

        self.page2.setLayout(layout2)
        self.addPage(self.page2)

        # Страница 3: Выбор расположения данных
        self.page3 = PathSelectionPage()
        self.addPage(self.page3)

        # Страница 4: Успех
        self.page4 = QWizardPage()
        self.page4.setTitle("Настройка завершена")
        self.page4.setFinalPage(True)
        layout4 = QVBoxLayout()

        success = QLabel("Настройка успешно завершена!")
        success.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        success.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout4.addWidget(success)

        wish = QLabel(
            "Теперь вы готовы к простой эмуляции игр на Steam Deck. "
            "Удачной игры!"
        )
        wish.setFont(QFont("Arial", 20))
        wish.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout4.addWidget(wish)
        layout4.addStretch()

        self.page4.setLayout(layout4)
        self.addPage(self.page4)

        # Применяем текущую тему и подписываемся
        self.apply_theme(theme_manager.current_theme)
        theme_manager.theme_changed.connect(self.apply_theme)
        self.theme_group.buttonToggled.connect(self.toggle_theme)
        self.currentIdChanged.connect(self.handle_page_change)

    def handle_page_change(self, page_id):
        back_btn = self.button(QWizard.WizardButton.BackButton)
        back_btn.setVisible(page_id != 0)

    def apply_theme(self, theme_name):
        try:
            self.setProperty("class", f"{theme_name}-theme")
            with open(THEME_FILE, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
            self.update_styles()
        except Exception as e:
            print(f"Ошибка применения темы: {e}")

    def update_styles(self):
        self.style().unpolish(self)
        self.style().polish(self)
        for btn_type in [QWizard.WizardButton.BackButton,
                         QWizard.WizardButton.NextButton,
                         QWizard.WizardButton.FinishButton]:
            btn = self.button(btn_type)
            if btn:
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                btn.update()

    def toggle_theme(self, button, checked):
        if checked:
            theme = 'dark' if button == self.dark_theme_btn else 'light'
            app_settings.set_theme(theme)
            theme_manager.set_theme(theme)

    def center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
