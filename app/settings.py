from PyQt6.QtCore import QSettings
import os

class AppSettings:
    def __init__(self):
        self._settings = None

    def _ensure_settings(self):
        if self._settings is None:
            # Создаем директорию для настроек, если ее нет
            config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, "settings.ini")
            # Инициализируем QSettings с указанием пути
            self._settings = QSettings(config_path, QSettings.Format.IniFormat)

    def get_theme(self):
        self._ensure_settings()
        return self._settings.value("theme", "dark", type=str)

    def set_theme(self, theme_name):
        self._ensure_settings()
        self._settings.setValue("theme", theme_name)

    def get_welcome_shown(self):
        self._ensure_settings()
        # Используем строковое представление для совместимости
        value = self._settings.value("welcome_shown", "false")
        return value.lower() == "true"

    def set_welcome_shown(self, shown):
        self._ensure_settings()
        self._settings.setValue("welcome_shown", "true" if shown else "false")

# Глобальный экземпляр настроек
app_settings = AppSettings()
