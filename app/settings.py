from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

class AppSettings:
    def __init__(self):
        self._settings = None
        
    def _ensure_settings(self):
        if self._settings is None:
            # Важно: создаем настройки перед первым использованием
            self._settings = QSettings("PixelDeck", "PixelDeck")
    
    def get_theme(self):
        self._ensure_settings()
        return self._settings.value("theme", "dark", type=str)
    
    def set_theme(self, theme_name):
        self._ensure_settings()
        self._settings.setValue("theme", theme_name)
    
    def get_welcome_shown(self):
        self._ensure_settings()
        # Используем 0 вместо False для лучшей совместимости
        return bool(int(self._settings.value("welcome_shown", 0)))
    
    def set_welcome_shown(self, shown):
        self._ensure_settings()
        # Сохраняем как целое число (1 или 0)
        self._settings.setValue("welcome_shown", int(shown))

# Глобальный экземпляр настроек
app_settings = AppSettings()
