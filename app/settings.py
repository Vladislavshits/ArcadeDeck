# settings.py
import os
from PyQt6.QtCore import QSettings

class AppSettings:
    def __init__(self):
        self.config_dir = os.path.join(os.path.expanduser("~"), "PixelDeck")
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_path = os.path.join(self.config_dir, "pixeldeck.ini")
        self.settings = QSettings(self.config_path, QSettings.Format.IniFormat)
    
    def get_theme(self):
        """Возвращает текущую тему ('dark' или 'light')"""
        return self.settings.value("theme", "dark", type=str)
    
    def set_theme(self, theme):
        """Устанавливает тему ('dark' или 'light')"""
        self.settings.setValue("theme", theme)
    
    def get_welcome_shown(self):
        """Показывалось ли приветственное окно"""
        return self.settings.value("welcome_shown", False, type=bool)
    
    def set_welcome_shown(self, shown):
        """Устанавливает флаг показа приветственного окна"""
        self.settings.setValue("welcome_shown", shown)

# Глобальный экземпляр настроек
app_settings = AppSettings()