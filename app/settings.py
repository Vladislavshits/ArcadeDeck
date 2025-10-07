from PyQt6.QtCore import QSettings
import os
from pathlib import Path

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

    # Настройки для пути users
    def get_users_path(self):
        self._ensure_settings()
        default_path = Path(__file__).parent / "users"
        return self._settings.value("users_path", str(default_path), type=str)

    def set_users_path(self, path):
        self._ensure_settings()
        self._settings.setValue("users_path", path)

    def get_users_path_type(self):
        self._ensure_settings()
        return self._settings.value("users_path_type", "default", type=str)

    def set_users_path_type(self, path_type):
        self._ensure_settings()
        self._settings.setValue("users_path_type", path_type)

    # Настройки для модуля разработчика
    def get_log_auto_scroll(self):
        self._ensure_settings()
        value = self._settings.value("Modules-dev-settings/auto_scroll", "true")
        return value.lower() == "true"

    def set_log_auto_scroll(self, enabled):
        self._ensure_settings()
        self._settings.setValue("Modules-dev-settings/auto_scroll", "true" if enabled else "false")

# Глобальный экземпляр настроек
app_settings = AppSettings()
