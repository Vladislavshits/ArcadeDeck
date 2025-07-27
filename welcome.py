from PyQt6.QtWidgets import QWizard, QWizardPage, QLabel, QVBoxLayout, QPushButton, QHBoxLayout, QButtonGroup, QApplication
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from settings import app_settings
import os
import sys

# Добавляем путь к корню проекта для импорта core
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from app.ui_assets.theme_manager import theme_manager
from core import THEME_FILE

class WelcomeWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добро пожаловать в PixelDeck!")
        self.setFixedSize(1000, 700)  # Увеличим размер для больших кнопок
        
        # Кнопки "Назад", "Далее" и "Готово"
        self.setButtonText(QWizard.WizardButton.BackButton, "Назад")
        self.setButtonText(QWizard.WizardButton.NextButton, "Далее")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Готово")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Пропустить настройку")
        
        # Страница 1: Приветствие
        self.page1 = QWizardPage()
        self.page1.setTitle("Добро пожаловать")
        layout1 = QVBoxLayout()
        title = QLabel("PixelDeck")
        title_font = QFont("Arial", 48, QFont.Weight.Bold)  # Увеличим шрифт
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout1.addWidget(title)
        
        desc = QLabel("Ваш помощник в настройке игр для Steam Deck")
        desc_font = QFont("Arial", 24)  # Увеличим шрифт
        desc.setFont(desc_font)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout1.addWidget(desc)
        
        self.page1.setLayout(layout1)
        self.addPage(self.page1)
        
        # Страница 2: Выбор темы
        self.page2 = QWizardPage()
        self.page2.setTitle("Выбор темы")
        layout2 = QVBoxLayout()
        
        theme_label = QLabel("Выберите предпочитаемую цветовую схему:")
        theme_label_font = QFont("Arial", 20)  # Увеличим шрифт
        theme_label.setFont(theme_label_font)
        theme_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout2.addWidget(theme_label)
        
        # Горизонтальный лейаут для кнопок тем
        buttons_layout = QHBoxLayout()
        
        # Группа кнопок для темы
        self.theme_group = QButtonGroup()
        
        # Кнопка темной темы
        self.dark_theme_btn = QPushButton("Темная тема")
        self.dark_theme_btn.setObjectName("themeButton")  # Идентификатор для стилей
        self.dark_theme_btn.setCheckable(True)
        self.dark_theme_btn.setFixedSize(300, 200)
        self.dark_theme_btn.setFont(QFont("Arial", 18))
        
        # Кнопка светлой темы
        self.light_theme_btn = QPushButton("Светлая тема")
        self.light_theme_btn.setObjectName("themeButton")  # Идентификатор для стилей
        self.light_theme_btn.setCheckable(True)
        self.light_theme_btn.setFixedSize(300, 200)
        self.light_theme_btn.setFont(QFont("Arial", 18))
        
        # Добавляем кнопки в группу
        self.theme_group.addButton(self.dark_theme_btn, 0)
        self.theme_group.addButton(self.light_theme_btn, 1)
        
        # По умолчанию выбрана темная тема
        self.dark_theme_btn.setChecked(True)
        
        buttons_layout.addWidget(self.dark_theme_btn)
        buttons_layout.addWidget(self.light_theme_btn)
        layout2.addLayout(buttons_layout)
        
        self.page2.setLayout(layout2)
        self.addPage(self.page2)

        # Применяем текущую тему
        self.apply_theme(theme_manager.current_theme)
        
        # Подписываемся на изменения темы
        theme_manager.theme_changed.connect(self.apply_theme)
        
        # Сигналы
        self.theme_group.buttonToggled.connect(self.toggle_theme)
        
        # Важно: при завершении мастера принимаем его
        self.button(QWizard.WizardButton.FinishButton).clicked.connect(self.accept)

        # Скрываем кнопку "Назад" на первом экране
        self.button(QWizard.WizardButton.BackButton).hide()
        
        # Обработчик смены страниц для управления видимостью кнопки "Назад"
        self.currentIdChanged.connect(self.handle_page_change)

    def handle_page_change(self, page_id):
        """Управляет видимостью кнопки 'Назад' в зависимости от страницы"""
        back_button = self.button(QWizard.WizardButton.BackButton)
        if page_id == 0:  # Первая страница (приветствие)
            back_button.hide()
        else:
            back_button.show()
        
    def apply_theme(self, theme_name):
        """Применяет указанную тему к окну"""
        try:
            # Загружаем стили из файла
            with open(THEME_FILE, 'r', encoding='utf-8') as f:
                stylesheet = f.read()
            
            # Устанавливаем свойство класса
            self.setProperty("class", f"{theme_name}-theme")
            
            # Применяем стили
            self.setStyleSheet(stylesheet)
            
            # Обновляем стили дочерних виджетов
            self.style().unpolish(self)
            self.style().polish(self)

            # Перерисовываем кнопки
            back_btn = self.button(QWizard.WizardButton.BackButton)
            next_btn = self.button(QWizard.WizardButton.NextButton)
            finish_btn = self.button(QWizard.WizardButton.FinishButton)
            cancel_btn = self.button(QWizard.WizardButton.CancelButton)
            
            if back_btn:
                back_btn.style().unpolish(back_btn)
                back_btn.style().polish(back_btn)
                back_btn.update()
                
            if next_btn:
                next_btn.style().unpolish(next_btn)
                next_btn.style().polish(next_btn)
                next_btn.update()
                
            if finish_btn:
                finish_btn.style().unpolish(finish_btn)
                finish_btn.style().polish(finish_btn)
                finish_btn.update()
                
            if cancel_btn:
                cancel_btn.style().unpolish(cancel_btn)
                cancel_btn.style().polish(cancel_btn)
                cancel_btn.update()
        except Exception as e:
            print(f"Ошибка применения темы: {e}")

    def toggle_theme(self, button, checked):
        if checked:
            if button == self.dark_theme_btn:
                theme = 'dark'
            else:
                theme = 'light'
            app_settings.set_theme(theme)
            
            app = QApplication.instance()
            if app:
                app.setProperty("class", theme + "-theme")
                # Перезагружаем глобальные стили
                try:
                    with open(THEME_FILE, 'r', encoding='utf-8') as f:
                        new_style = f.read()
                    app.setStyleSheet(new_style)
                except Exception as e:
                    print(f"Ошибка перезагрузки стилей: {e}")
        
    def center_on_screen(self):
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)
