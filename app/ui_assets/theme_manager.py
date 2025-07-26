# theme_manager.py
from PyQt6.QtCore import QObject, pyqtSignal

class ThemeManager(QObject):
    """Централизованный менеджер тем с сигналами"""
    theme_changed = pyqtSignal(str)  # Сигнал с именем темы
    
    def __init__(self):
        super().__init__()
        self._current_theme = "dark"
    
    @property
    def current_theme(self) -> str:
        """Текущая активная тема"""
        return self._current_theme
    
    def set_theme(self, theme_name: str):
        """Устанавливает новую тему и оповещает подписчиков"""
        if theme_name not in ["dark", "light"]:
            raise ValueError(f"Недопустимое имя темы: {theme_name}")
        
        if theme_name != self._current_theme:
            self._current_theme = theme_name
            self.theme_changed.emit(theme_name)

# Глобальный экземпляр менеджера тем
theme_manager = ThemeManager()
