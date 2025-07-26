from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton, 
    QStackedWidget, QButtonGroup, QRadioButton, QCheckBox
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QIcon
import sys
import os
from settings import app_settings

class WelcomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Заголовок
        title = QLabel("Добро пожаловать в PixelDeck!")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(24)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Описание
        description = QLabel(
            "Эта программа разрабатывается для автоматизации процесса эмуляции, "
            "автоустановки игр, а так же многое другое ждет вас в будущем!\n\n"
            "Приятного пользования!"
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setWordWrap(True)
        description_font = QFont()
        description_font.setPointSize(14)
        description.setFont(description_font)
        layout.addWidget(description)
        
        layout.addStretch(1)
        
        # Кнопка GitHub
        github_button = QPushButton("Проект на GitHub")
        github_button.setFixedHeight(50)
        github_button.clicked.connect(self.open_github)
        layout.addWidget(github_button)
        
    def open_github(self):
        import webbrowser
        webbrowser.open("https://github.com/Vladislavshits/PixelDeck")

class ThemePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()
        
        # Загружаем текущую тему
        current_theme = app_settings.get_theme()
        # Устанавливаем состояние переключателя на основе текущей темы
        if current_theme == 'dark':
            self.dark_radio.setChecked(True)
        else:
            self.light_radio.setChecked(True)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Заголовок
        title = QLabel("Выбор темы")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(24)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Описание
        description = QLabel(
            "Выберите предпочитаемую тему интерфейса. Вы всегда можете изменить это в настройках позже."
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setWordWrap(True)
        description_font = QFont()
        description_font.setPointSize(14)
        description.setFont(description_font)
        layout.addWidget(description)
        
        # Группа переключателей
        theme_group = QWidget()
        theme_layout = QVBoxLayout(theme_group)
        theme_layout.setContentsMargins(50, 30, 50, 30)
        
        self.dark_radio = QRadioButton("Тёмная тема")
        self.light_radio = QRadioButton("Светлая тема")
        
        theme_layout.addWidget(self.dark_radio)
        theme_layout.addWidget(self.light_radio)
        
        # Группа для исключительного выбора
        self.theme_group = QButtonGroup(self)
        self.theme_group.addButton(self.dark_radio)
        self.theme_group.addButton(self.light_radio)
        
        layout.addWidget(theme_group)
        layout.addStretch(1)
        
        # Подключаем обработчики
        self.dark_radio.toggled.connect(self.toggle_theme)
        self.light_radio.toggled.connect(self.toggle_theme)
    
    def toggle_theme(self, checked):
        """Обработчик изменения темы"""
        if not checked:
            return
        theme = 'dark' if self.dark_radio.isChecked() else 'light'
        app_settings.set_theme(theme)
        
        # Применяем новую тему
        app = QApplication.instance()
        app.setProperty("class", f"{theme}-theme")
        
        # Перезагружаем стили (если они уже были загружены)
        if hasattr(app, 'stylesheet'):
            app.setStyleSheet("")
            app.setStyleSheet(app.stylesheet)

class EmulatorPage(QWidget):
    """Страница выбора эмуляторов"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        title = QLabel("Настройка эмуляторов")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(24)
        title.setFont(title_font)
        layout.addWidget(title)
        
        description = QLabel(
            "Выберите эмуляторы, которые вы хотите настроить. "
            "Вы всегда сможете добавить другие позже в настройках."
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setWordWrap(True)
        layout.addWidget(description)
        
        # Чекбоксы для эмуляторов
        emulator_group = QWidget()
        emulator_layout = QVBoxLayout(emulator_group)
        emulator_layout.setContentsMargins(50, 30, 50, 30)
        
        self.emulators = {
            "Dolphin": QCheckBox("Dolphin (GameCube/Wii)"),
            "PCSX2": QCheckBox("PCSX2 (PlayStation 2)"),
            "RPCS3": QCheckBox("RPCS3 (PlayStation 3)"),
            "Yuzu": QCheckBox("Yuzu (Nintendo Switch)"),
            "Cemu": QCheckBox("Cemu (Wii U)"),
        }
        
        for emulator in self.emulators.values():
            emulator_layout.addWidget(emulator)
        
        layout.addWidget(emulator_group)
        layout.addStretch(1)

class CompletionPage(QWidget):
    """Страница завершения настройки"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        title = QLabel("Настройка завершена!")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(24)
        title.setFont(title_font)
        layout.addWidget(title)
        
        description = QLabel(
            "Вы успешно завершили первоначальную настройку PixelDeck. "
            "Теперь вы можете начать пользоваться всеми возможностями приложения.\n\n"
            "Приятной игры!"
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setWordWrap(True)
        layout.addWidget(description)
        
        layout.addStretch(1)

class WelcomeWizard(QDialog):
    def __init__(self, dark_theme=True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добро пожаловать в PixelDeck!")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)  # Без рамки
        self.resize(800, 600)  # Начальный размер, но можно сделать на весь экран
        
        # Устанавливаем флаг, чтобы окно было модальным и на весь экран
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        # Основной лэйаут
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Стековый виджет для страниц
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget, 1)  # Растягиваем
        
        # Создаем страницы
        self.pages = [
            WelcomePage(),
            ThemePage(self),
            EmulatorPage(),
            CompletionPage()
        ]
        for page in self.pages:
            self.stacked_widget.addWidget(page)
        
        # Панель навигации (кнопки внизу)
        nav_widget = QWidget()
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(20, 10, 20, 20)
        
        # Кнопки
        self.back_button = QPushButton("Назад")
        self.back_button.setIcon(QIcon.fromTheme("go-previous"))
        self.back_button.setEnabled(False)
        
        self.next_button = QPushButton("Далее")
        self.next_button.setIcon(QIcon.fromTheme("go-next"))
        
        self.skip_button = QPushButton("Пропустить")
        self.finish_button = QPushButton("Готово")
        self.finish_button.setVisible(False)
        
        # Добавляем кнопки
        nav_layout.addWidget(self.back_button)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.skip_button)
        nav_layout.addWidget(self.next_button)
        nav_layout.addWidget(self.finish_button)
        
        main_layout.addWidget(nav_widget)
        
        # Подключаем обработчики
        self.back_button.clicked.connect(self.go_back)
        self.next_button.clicked.connect(self.go_next)
        self.skip_button.clicked.connect(self.skip)
        self.finish_button.clicked.connect(self.accept)
        
        # Текущая страница
        self.current_index = 0
    
    def go_back(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.stacked_widget.setCurrentIndex(self.current_index)
            self.update_buttons()
    
    def go_next(self):
        if self.current_index < len(self.pages) - 1:
            self.current_index += 1
            self.stacked_widget.setCurrentIndex(self.current_index)
            self.update_buttons()
        else:
            self.accept()
    
    def skip(self):
        self.accept()
    
    def update_buttons(self):
        # Обновляем состояние кнопки "Назад"
        self.back_button.setEnabled(self.current_index > 0)
        
        # Если это последняя страница, меняем "Далее" на "Готово"
        if self.current_index == len(self.pages) - 1:
            self.next_button.setVisible(False)
            self.finish_button.setVisible(True)
            self.skip_button.setVisible(False)
        else:
            self.next_button.setVisible(True)
            self.finish_button.setVisible(False)
            self.skip_button.setVisible(True)
    
    def center_on_screen(self):
        """Центрирует окно на экране."""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.geometry()
            self.setGeometry(
                screen_geometry.x(),
                screen_geometry.y(),
                screen_geometry.width(),
                screen_geometry.height()
            )

if __name__ == "__main__":
    # Для тестирования отдельно
    app = QApplication(sys.argv)
    wizard = WelcomeWizard()
    wizard.center_on_screen()  # Растягиваем на весь экран
    wizard.show()
    sys.exit(app.exec())
