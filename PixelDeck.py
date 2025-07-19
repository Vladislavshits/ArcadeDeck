#!/usr/bin/env python3
# Импорт необходимых модулей
import sys
import webbrowser
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QListWidget, QListWidgetItem, QLabel, QPushButton, QDialog,
    QSizePolicy, QSpacerItem, QDesktopWidget, QToolButton, QFrame,
    QCheckBox, QMessageBox
)
from PyQt5.QtCore import Qt, QSize, QTimer, QSettings, QFile, QTextStream
from PyQt5.QtGui import QIcon, QFont, QColor, QPalette

# Версия приложения
APP_VERSION = "0.1.5"

# --- ПУТИ К ФАЙЛАМ ---
# Базовый путь к директории контента (установка в ~/PixelDeck/Content)
CONTENT_DIR = os.path.join(os.path.expanduser("~"), "PixelDeck", "Content")
# Пути к JSON-файлам с гайдами
GUIDES_JSON_PATH = os.path.join(CONTENT_DIR, "guides.json")
GAME_LIST_GUIDE_JSON_PATH = os.path.join(CONTENT_DIR, "game-list-guides.json")
# Директория со стилями (в домашней директории пользователя: ~/PixelDeck/data/style)
STYLES_DIR = os.path.join(os.path.expanduser("~"), "PixelDeck", "data", "style")

# Пути к файлам стилей для разных окон и тем
MAIN_WINDOW_DARK_STYLE = os.path.join(STYLES_DIR, "main_window_dark.qss")
MAIN_WINDOW_LIGHT_STYLE = os.path.join(STYLES_DIR, "main_window_light.qss")
WELCOME_DIALOG_DARK_STYLE = os.path.join(STYLES_DIR, "welcome_dialog_dark.qss")
WELCOME_DIALOG_LIGHT_STYLE = os.path.join(STYLES_DIR, "welcome_dialog_light.qss")
SETTINGS_DIALOG_DARK_STYLE = os.path.join(STYLES_DIR, "settings_dialog_dark.qss")
SETTINGS_DIALOG_LIGHT_STYLE = os.path.join(STYLES_DIR, "settings_dialog_light.qss")

# Создаем необходимые директории, если они не существуют
os.makedirs(CONTENT_DIR, exist_ok=True)
os.makedirs(STYLES_DIR, exist_ok=True)

def load_content():
    """
    Загружает контент из JSON-файлов (guides.json и game-list-guides.json).
    Возвращает два списка: гайды и игры.
    """
    guides = []
    games = []

    # Проверяем существование папки Content
    if not os.path.exists(CONTENT_DIR):
        print(f"Папка контента не найдена: {CONTENT_DIR}")
        return guides, games

    # Загрузка гайдов
    try:
        if os.path.exists(GUIDES_JSON_PATH):
            print(f"Загрузка файла гайдов: {GUIDES_JSON_PATH}")
            with open(GUIDES_JSON_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
                if content:
                    guides_data = json.loads(content)
                    if isinstance(guides_data, list):
                        guides = guides_data
                        print(f"Загружено гайдов: {len(guides)}")
                    else:
                        print(f"Ошибка: файл гайдов не содержит список")
                else:
                    print(f"Файл гайдов пуст: {GUIDES_JSON_PATH}")
        else:
            print(f"Файл гайдов не найден: {GUIDES_JSON_PATH}")
    except json.JSONDecodeError as e:
        print(f"Ошибка декодирования JSON в файле гайдов: {e}")
    except Exception as e:
        print(f"Ошибка загрузки гайдов: {e}")

    # Загрузка списка игр
    try:
        if os.path.exists(GAME_LIST_GUIDE_JSON_PATH):
            print(f"Загрузка файла игр: {GAME_LIST_GUIDE_JSON_PATH}")
            with open(GAME_LIST_GUIDE_JSON_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
                if content:
                    games_data = json.loads(content)
                    if isinstance(games_data, list):
                        games = games_data
                        print(f"Загружено игр: {len(games)}")
                    else:
                        print(f"Ошибка: файл игр не содержит список")
                else:
                    print(f"Файл игр пуст: {GAME_LIST_GUIDE_JSON_PATH}")
        else:
            print(f"Файл игр не найден: {GAME_LIST_GUIDE_JSON_PATH}")
    except json.JSONDecodeError as e:
        print(f"Ошибка декодирования JSON в файле игр: {e}")
    except Exception as e:
        print(f"Ошибка загрузки игр: {e}")

    return guides, games

# Загружаем контент
GUIDES, GAMES = load_content()

def load_stylesheet(filename):
    """
    Загружает файл стилей (QSS) и возвращает его содержимое в виде строки.
    Если файл не найден или не может быть открыт, возвращает пустую строку.
    """
    file = QFile(filename)
    # Проверяем существование файла
    if not file.exists():
        print(f"Файл стиля не найден: {filename}")
        return ""

    # Пытаемся открыть файл для чтения
    if file.open(QFile.ReadOnly | QFile.Text):
        stream = QTextStream(file)
        stylesheet = stream.readAll()
        file.close()
        return stylesheet
    return ""

def show_style_error(missing_styles):
    """
    Показывает диалоговое окно с ошибкой отсутствия файлов стилей.

    :param missing_styles: Список отсутствующих файлов стилей
    """
    # Создаем диалоговое окно с ошибкой
    error_dialog = QMessageBox()
    error_dialog.setWindowTitle("Ошибка запуска! Код #1!")
    error_dialog.setIcon(QMessageBox.Critical)

    # Формируем текст сообщения
    message = "Отсутствуют файлы стилей. Переустановите программу с сайта проекта.\n\n"
    message += "Отсутствующие файлы:\n"
    for style in missing_styles:
        message += f"- {os.path.basename(style)}\n"

    error_dialog.setText(message)

    # Добавляем кнопки
    download_button = error_dialog.addButton("Скачать установщик", QMessageBox.ActionRole)
    close_button = error_dialog.addButton("Закрыть", QMessageBox.RejectRole)

    # Показываем диалог
    error_dialog.exec_()

    # Обрабатываем нажатие кнопок
    if error_dialog.clickedButton() == download_button:
        webbrowser.open("https://github.com/Vladislavshits/PixelDeck/releases/download/v0.1.5/install.pixeldeck.sh")

    return False

class WelcomeDialog(QDialog):
    """Диалоговое окно приветствия, показываемое при первом запуске приложения."""

    def __init__(self, parent=None, dark_theme=True):
        """
        Инициализация диалога приветствия.

        :param parent: Родительское окно
        :param dark_theme: Использовать темную тему (по умолчанию True)
        """
        super().__init__(parent, Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        # Настройка окна
        self.setWindowTitle("Добро пожаловать в PixelDeck")
        self.setFixedSize(720, 450)
        self.dark_theme = dark_theme

        # Основной вертикальный лэйаут
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # Заголовок
        title = QLabel("Добро пожаловать в PixelDeck!")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(22)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        main_layout.addStretch(1)  # Гибкий промежуток

        # Текст с инструкцией
        text = QLabel(
            "Привет! Чтобы использовать эту программу без проблем, установи в настройках Steam Deck свой браузер по умолчанию.\n\n"
            "Как это сделать?\n"
            "1. Открыть \"Настройки\"\n"
            "2. В левой колонке долистать до пункта \"Приложения по умолчанию\"\n"
            "3. Установить браузер по умолчанию и применить изменения."
        )
        text.setWordWrap(True)  # Перенос текста
        text.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(text)

        main_layout.addStretch(1)  # Гибкий промежуток

        # Контейнер для кнопки
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.addStretch(1)

        # Кнопка "Продолжить"
        self.continue_button = QPushButton("Продолжить")
        self.continue_button.setFixedSize(200, 50)
        self.continue_button.clicked.connect(self.accept)  # Закрывает диалог с кодом Accepted
        button_layout.addWidget(self.continue_button)
        button_layout.addStretch(1)

        main_layout.addWidget(button_container)
        # Применяем выбранную тему
        self.apply_theme()

    def apply_theme(self):
        """Применяет выбранную тему (темную или светлую) к диалогу."""
        if self.dark_theme:
            style = load_stylesheet(WELCOME_DIALOG_DARK_STYLE)
        else:
            style = load_stylesheet(WELCOME_DIALOG_LIGHT_STYLE)

        if style:
            self.setStyleSheet(style)

    def center_on_screen(self):
        """Центрирует окно на экране."""
        screen = QDesktopWidget().screenGeometry()
        window = self.geometry()
        self.move(
            (screen.width() - window.width()) // 2,
            (screen.height() - window.height()) // 2
        )

class SettingsDialog(QDialog):
    """Диалоговое окно настроек приложения."""

    def __init__(self, parent=None, dark_theme=True):
        """
        Инициализация диалога настроек.

        :param parent: Родительское окно
        :param dark_theme: Использовать темную тему (по умолчанию True)
        """
        super().__init__(parent, Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        # Настройка окна
        self.setWindowTitle("Настройки PixelDeck")
        self.setFixedSize(400, 250)
        self.dark_theme = dark_theme
        self.parent = parent  # Ссылка на родительское окно

        # Основной вертикальный лэйаут
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # Заголовок
        title = QLabel("Настройки")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(28)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Лэйаут для переключателя темы
        theme_layout = QHBoxLayout()
        theme_layout.setContentsMargins(10, 0, 10, 0)

        # Метка для переключателя
        theme_label = QLabel("Темная тема:")
        theme_label.setFont(QFont("Arial", 14))
        theme_layout.addWidget(theme_label)

        theme_layout.addStretch(1)  # Гибкий промежуток

        # Переключатель темы (чекбокс)
        self.theme_toggle = QCheckBox()
        self.theme_toggle.setChecked(dark_theme)
        self.theme_toggle.setFixedSize(60, 30)
        # Подключаем обработчик изменения состояния
        self.theme_toggle.toggled.connect(self.toggle_theme)
        theme_layout.addWidget(self.theme_toggle)

        main_layout.addLayout(theme_layout)

        main_layout.addStretch(1)  # Гибкий промежуток

        # Метка с версией приложения
        version_label = QLabel(f"PixelDeck Версия {APP_VERSION}")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setObjectName("versionLabel")  # Имя объекта для стилизации
        main_layout.addWidget(version_label)

        # Лэйаут для кнопки
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)

        # Кнопка "Закрыть"
        close_button = QPushButton("Закрыть")
        close_button.setFixedSize(120, 40)
        close_button.clicked.connect(self.accept)  # Закрывает диалог с кодом Accepted
        button_layout.addWidget(close_button)

        button_layout.addStretch(1)
        main_layout.addLayout(button_layout)

        # Применяем выбранную тему
        self.apply_theme()

    def toggle_theme(self, checked):
        """
        Обработчик изменения состояния переключателя темы.

        :param checked: Новое состояние переключателя (включена темная тема)
        """
        self.dark_theme = checked
        # Обновляем тему текущего диалога
        self.apply_theme()

        if self.parent:
            # Обновляем тему родительского окна
            self.parent.dark_theme = checked
            self.parent.apply_theme()

            # Сохраняем настройку темы в конфигурационный файл
            config_dir = os.path.join(os.path.expanduser("~"), "PixelDeck")
            config_path = os.path.join(config_dir, "pixeldeck.ini")
            settings = QSettings(config_path, QSettings.IniFormat)
            settings.setValue("dark_theme", checked)

    def apply_theme(self):
        """Применяет выбранную тему (темную или светлую) к диалогу настроек."""
        if self.dark_theme:
            style = load_stylesheet(SETTINGS_DIALOG_DARK_STYLE)
        else:
            style = load_stylesheet(SETTINGS_DIALOG_LIGHT_STYLE)

        if style:
            self.setStyleSheet(style)

class PixelDeckApp(QMainWindow):
    """Главное окно приложения PixelDeck."""

    def __init__(self, dark_theme=True):
        """
        Инициализация главного окна приложения.

        :param dark_theme: Использовать темную тему (по умолчанию True)
        """
        super().__init__()
        # Настройка окна
        self.setWindowTitle("PixelDeck")
        self.setGeometry(400, 300, 800, 600)
        self.setMinimumSize(QSize(600, 400))
        self.dark_theme = dark_theme

        # Устанавливаем иконку приложения
        self.setWindowIcon(QIcon.fromTheme("system-search"))

        # Создаем центральный виджет и основной лэйаут
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.main_layout = QVBoxLayout(main_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 10)

        # Верхняя панель с кнопкой настроек
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        # Кнопка настроек
        self.settings_button = QToolButton()
        self.settings_button.setFixedSize(40, 40)
        self.settings_button.setIcon(QIcon.fromTheme("preferences-system"))
        self.settings_button.setIconSize(QSize(24, 24))
        self.settings_button.clicked.connect(self.open_settings)
        top_bar.addWidget(self.settings_button)
        top_bar.addStretch(1)  # Гибкий промежуток

        self.main_layout.addLayout(top_bar)
        self.main_layout.addStretch(1)  # Гибкий промежуток

        # Заголовок приложения
        title = QLabel("PixelDeck")
        title.setObjectName("title")  # Имя объекта для стилизации
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(28)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(title, alignment=Qt.AlignCenter)

        self.main_layout.addSpacing(30)  # Фиксированный промежуток

        # Поле поиска
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Поиск гайдов и игр...")
        self.search_field.setClearButtonEnabled(True)  # Кнопка очистки
        # Подключаем обработчик изменения текста
        self.search_field.textChanged.connect(self.search_content)
        self.search_field.setMinimumHeight(60)
        self.main_layout.addWidget(self.search_field, alignment=Qt.AlignCenter)

        self.main_layout.addSpacing(20)  # Фиксированный промежуток

        # Список результатов поиска
        self.results_list = QListWidget()
        # Подключаем обработчик двойного клика по элементу
        self.results_list.itemDoubleClicked.connect(self.open_item)
        self.results_list.hide()  # Скрываем список до начала поиска
        self.main_layout.addWidget(self.results_list, 1, alignment=Qt.AlignCenter)

        self.main_layout.addStretch(1)  # Гибкий промежуток

        # Применяем выбранную тему
        self.apply_theme()

    def apply_theme(self):
        """Применяет выбранную тему (темную или светлую) к главному окну."""
        if self.dark_theme:
            style = load_stylesheet(MAIN_WINDOW_DARK_STYLE)
        else:
            style = load_stylesheet(MAIN_WINDOW_LIGHT_STYLE)

        if style:
            self.setStyleSheet(style)

    def open_settings(self):
        """Открывает диалоговое окно настроек."""
        settings_dialog = SettingsDialog(self, self.dark_theme)
        settings_dialog.setModal(True)  # Модальный режим
        settings_dialog.exec_()  # Показываем диалог

    def display_results(self, results):
        """
        Отображает результаты поиска в виджете списка.

        :param results: Список результатов (каждый элемент - словарь с ключами 'type', 'title', 'url')
        """
        self.results_list.clear()  # Очищаем предыдущие результаты
        # Если результатов нет, скрываем виджет
        if not results:
            self.results_list.hide()
            return

        # Добавляем каждый результат в список
        for item in results:
            list_item = QListWidgetItem()

            # Создаем виджет для отображения результата
            item_widget = QWidget()
            item_layout = QVBoxLayout(item_widget)

            # Заголовок
            title_label = QLabel(item['title'])
            title_font = QFont("Arial", 14)
            title_font.setBold(True)
            title_label.setFont(title_font)

            # Тип (гайд или игра)
            type_label = QLabel(f"Тип: {item['type']}")
            type_label.setFont(QFont("Arial", 10))
            if item['type'] == "Гайд":
                type_label.setStyleSheet("color: #4CAF50;")
            else:
                type_label.setStyleSheet("color: #2196F3;")

            item_layout.addWidget(title_label)
            item_layout.addWidget(type_label)

            # Устанавливаем виджет в элемент списка
            list_item.setSizeHint(item_widget.sizeHint())
            self.results_list.addItem(list_item)
            self.results_list.setItemWidget(list_item, item_widget)

            # Сохраняем URL в пользовательских данных элемента
            list_item.setData(Qt.UserRole, item['url'])

        # Показываем виджет с результатами
        self.results_list.show()
        self.results_list.updateGeometry()  # Обновляем геометрию виджета

    def search_content(self, text):
        """
        Обработчик изменения текста в поле поиска.
        Использует таймер для отложенного поиска.

        :param text: Текст для поиска
        """
        # Запускаем поиск через 100 мс для оптимизации
        QTimer.singleShot(100, lambda: self.perform_search(text))

    def perform_search(self, text):
        """
        Выполняет поиск по гайдам и играм.

        :param text: Текст для поиска
        """
        # Если поле поиска пустое, скрываем результаты
        if not text.strip():
            self.results_list.hide()
            return

        # Приводим запрос к нижнему регистру для регистронезависимого поиска
        query = text.lower()
        results = []

        # Поиск в гайдах
        for guide in GUIDES:
            if query in guide["title"].lower():
                results.append({
                    'type': 'Гайд',
                    'title': guide["title"],
                    'url': guide["url"]
                })

        # Поиск в играх
        for game in GAMES:
            if query in game["title"].lower():
                results.append({
                    'type': 'Игра',
                    'title': game["title"],
                    'url': game["url"]
                })

        # Отображаем результаты
        self.display_results(results)

    def open_item(self, item):
        """
        Открывает выбранный элемент в браузере по умолчанию.

        :param item: Элемент списка, по которому кликнули
        """
        # Получаем URL из пользовательских данных элемента
        url = item.data(Qt.UserRole)
        # Открываем URL в браузере по умолчанию
        webbrowser.open(url)

# Точка входа в приложение
if __name__ == "__main__":
    # Создаем экземпляр приложения
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Устанавливаем стиль Fusion

    # --- ПРОВЕРКА НАЛИЧИЯ ФАЙЛОВ СТИЛЕЙ ---
    # Список обязательных файлов стилей
    required_styles = [
        MAIN_WINDOW_DARK_STYLE,
        MAIN_WINDOW_LIGHT_STYLE,
        WELCOME_DIALOG_DARK_STYLE,
        WELCOME_DIALOG_LIGHT_STYLE,
        SETTINGS_DIALOG_DARK_STYLE,
        SETTINGS_DIALOG_LIGHT_STYLE
    ]

    # Проверяем наличие каждого файла стиля
    missing_styles = [style for style in required_styles if not os.path.exists(style)]

    # Если директория со стилями не существует, считаем все стили отсутствующими
    if not os.path.exists(STYLES_DIR):
        missing_styles = required_styles

    # Если какие-то файлы отсутствуют
    if missing_styles:
        # Показываем диалог с ошибкой
        show_style_error(missing_styles)
        sys.exit(1)  # Выходим с ошибкой

    # --- НАСТРОЙКА КОНФИГУРАЦИИ ПРИЛОЖЕНИЯ ---
    # Создаем каталог для настроек в домашней директории пользователя
    config_dir = os.path.join(os.path.expanduser("~"), "PixelDeck")
    os.makedirs(config_dir, exist_ok=True)  # Создаем, если не существует

    # Путь к файлу настроек
    config_path = os.path.join(config_dir, "pixeldeck.ini")
    # Создаем объект для работы с настройками
    settings = QSettings(config_path, QSettings.IniFormat)

    # Читаем настройки
    welcome_shown = settings.value("welcome_shown", False, type=bool)
    dark_theme = settings.value("dark_theme", True, type=bool)

    # Если приветственное окно еще не показывалось
    if not welcome_shown:
        # Создаем и показываем приветственное окно
        welcome = WelcomeDialog(dark_theme=dark_theme)
        welcome.center_on_screen()  # Центрируем на экране
        # Если пользователь нажал "Продолжить"
        if welcome.exec_() == QDialog.Accepted:
            # Сохраняем флаг, что окно было показано
            settings.setValue("welcome_shown", True)

    # Создаем и показываем главное окно приложения
    window = PixelDeckApp(dark_theme=dark_theme)
    window.showMaximized()  # Показываем в полноэкранном режиме

    # Запускаем главный цикл обработки событий
    sys.exit(app.exec_())
