import os
import sys
from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QLabel, QVBoxLayout, QPushButton,
    QHBoxLayout, QButtonGroup, QFrame, QApplication
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from settings import app_settings
from app.ui_assets.theme_manager import theme_manager
from core import THEME_FILE

class WelcomeWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добро пожаловать в PixelDeck!")
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
        title = QLabel("PixelDeck")
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

        # Страница 3: Успех
        self.page3 = QWizardPage()
        self.page3.setTitle("Настройка завершена")
        self.page3.setFinalPage(True)
        layout3 = QVBoxLayout()

        success = QLabel("Настройка успешно завершена!")
        success.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        success.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout3.addWidget(success)

        wish = QLabel("Теперь вы готовы к простой эмуляции игр на Steam Deck. Удачных игр!")
        wish.setFont(QFont("Arial", 20))
        wish.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout3.addWidget(wish)
        layout3.addStretch()

        self.page3.setLayout(layout3)
        self.addPage(self.page3)

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