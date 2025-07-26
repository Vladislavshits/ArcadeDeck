from PyQt6.QtCore import QSettings

class AppSettings:
    def __init__(self):
        # Инициализация QSettings будет отложена до первого вызова
        self._settings = None
        
    def _ensure_settings(self):
        """Обеспечивает инициализацию QSettings"""
        if self._settings is None:
            self._settings = QSettings("PixelDeck", "PixelDeck")
    
    def get_theme(self):
        self._ensure_settings()
        return self._settings.value("theme", "dark", type=str)
    
    def set_theme(self, theme_name):
        self._ensure_settings()
        self._settings.setValue("theme", theme_name)
        # Обновляем глобальную тему приложения
        app = QApplication.instance()
        if app:
            app.setProperty("class", f"{theme_name}-theme")
            # Перезагружаем стили
            app.setStyleSheet("")
            app.setStyleSheet(global_stylesheet)
    
    def get_welcome_shown(self):
        self._ensure_settings()
        return self._settings.value("welcome_shown", False, type=bool)
    
    def set_welcome_shown(self, shown):
        self._ensure_settings()
        self._settings.setValue("welcome_shown", shown)

# Глобальный экземпляр настроек
app_settings = AppSettings()
