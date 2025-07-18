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
# Базовый путь к директории скрипта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Путь к JSON-файлу с гайдами
GUIDES_JSON_PATH = os.path.join(BASE_DIR, "guides.json")
# Директория со стилями (в домашней директории пользователя: ~/PixelDeck/data/style)
STYLES_DIR = os.path.join(os.path.expanduser("~"), "PixelDeck", "data", "style")

# Пути к файлам стилей для разных окон и тем
MAIN_WINDOW_DARK_STYLE = os.path.join(STYLES_DIR, "main_window_dark.qss")
MAIN_WINDOW_LIGHT_STYLE = os.path.join(STYLES_DIR, "main_window_light.qss")
WELCOME_DIALOG_DARK_STYLE = os.path.join(STYLES_DIR, "welcome_dialog_dark.qss")
WELCOME_DIALOG_LIGHT_STYLE = os.path.join(STYLES_DIR, "welcome_dialog_light.qss")
SETTINGS_DIALOG_DARK_STYLE = os.path.join(STYLES_DIR, "settings_dialog_dark.qss")
SETTINGS_DIALOG_LIGHT_STYLE = os.path.join(STYLES_DIR, "settings_dialog_light.qss")

def load_guides():
    """
    Загружает гайды из JSON-файла.
    Если файл не найден или произошла ошибка, возвращает список по умолчанию.
    """
    try:
        # Проверяем существование файла с гайдами
        if os.path.exists(GUIDES_JSON_PATH):
            # Открываем и читаем JSON-файл
            with open(GUIDES_JSON_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        # В случае ошибки выводим сообщение в консоль
        print(f"Ошибка загрузки guides.json: {e}")

    # Возвращаем список по умолчанию, если файл не найден или произошла ошибка
    return [
        {"title": "EmuDeck: Полное руководство по установке", "url": "https://example.com/emudeck"},
        {"title": "Настройка эмулятора Yuzu", "url": "https://example.com/yuzu"},
        {"title": "RPCS3 на Steam Deck", "url": "https://example.com/rpcs3"},
        {"title": "Оптимизация CEMU", "url": "https://example.com/cemu"},
        {"title": "Настройка эмулятора Dolphin", "url": "https://example.com/dolphin"},
        {"title": "Эмуляция PS2 с PCSX2", "url": "https://example.com/pcsx2"},
        {"title": "Vita3K для игр с PlayStation Vita", "url": "https://example.com/vita3k"},
        {"title": "Игры Switch на Steam Deck", "url": "https://example.com/switch"},
        {"title": "Эмуляция Xbox: руководство по Xemu", "url": "https://example.com/xemu"},
        {"title": "Настройка ядер RetroArch", "url": "https://example.com/retroarch"},
        {"title": "Настройка контроллера GameCube", "url": "https://example.com/gc_controller"},
        {"title": "Конфигурация Steam ROM Manager", "url": "https://example.com/srm"},
        {"title": "Оптимизация производительности", "url": "https://example.com/performance"},
        {"title": "Облачные сохранения для эмуляторов", "url": "https://example.com/cloud_saves"},
        {"title": "Сравнение эмуляторов Windows", "url": "https://example.com/windows_emu"},
    ]

# Загружаем список гайдов
GUIDES = load_guides()

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
        self.search_field.setPlaceholderText("Поиск гайдов...")
        self.search_field.setClearButtonEnabled(True)  # Кнопка очистки
        # Подключаем обработчик изменения текста
        self.search_field.textChanged.connect(self.search_guides)
        self.search_field.setMinimumHeight(60)
        self.main_layout.addWidget(self.search_field, alignment=Qt.AlignCenter)

        self.main_layout.addSpacing(20)  # Фиксированный промежуток

        # Список результатов поиска
        self.results_list = QListWidget()
        # Подключаем обработчик двойного клика по элементу
        self.results_list.itemDoubleClicked.connect(self.open_guide)
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

    def display_guides(self, guides):
        """
        Отображает список гайдов в виджете результатов.

        :param guides: Список гайдов для отображения
        """
        self.results_list.clear()  # Очищаем предыдущие результаты
        # Если гайдов нет, скрываем виджет
        if not guides:
            self.results_list.hide()
            return

        # Добавляем каждый гайд в список
        for guide in guides:
            item = QListWidgetItem(guide["title"])
            # Сохраняем URL в пользовательских данных элемента
            item.setData(Qt.UserRole, guide["url"])
            item.setFont(QFont("Arial", 14))  # Устанавливаем шрифт
            self.results_list.addItem(item)

        # Показываем виджет с результатами
        self.results_list.show()
        self.results_list.updateGeometry()  # Обновляем геометрию виджета

    def search_guides(self, text):
        """
        Обработчик изменения текста в поле поиска.
        Использует таймер для отложенного поиска.

        :param text: Текст для поиска
        """
        # Запускаем поиск через 100 мс для оптимизации
        QTimer.singleShot(100, lambda: self.perform_search(text))

    def perform_search(self, text):
        """
        Выполняет поиск гайдов по введенному тексту.

        :param text: Текст для поиска
        """
        # Если поле поиска пустое, скрываем результаты
        if not text.strip():
            self.results_list.hide()
            return

        # Приводим запрос к нижнему регистру для регистронезависимого поиска
        query = text.lower()
        # Фильтруем гайды по вхождению запроса в заголовок
        results = [guide for guide in GUIDES if query in guide["title"].lower()]
        # Отображаем результаты
        self.display_guides(results)

    def open_guide(self, item):
        """
        Открывает выбранный гайд в браузере по умолчанию.

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
    # Проверяем существование директории со стилями
    if not os.path.exists(STYLES_DIR):
        # Если директория не существует, считаем все стили отсутствующими
        missing_styles = [
            "main_window_dark.qss", "main_window_light.qss",
            "welcome_dialog_dark.qss", "welcome_dialog_light.qss",
            "settings_dialog_dark.qss", "settings_dialog_light.qss"
        ]
        show_style_error(missing_styles)
        sys.exit(1)  # Выходим с ошибкой

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
