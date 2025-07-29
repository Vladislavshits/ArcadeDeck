from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtWidgets import QWidget, QApplication
import logging
from pathlib import Path

# Инициализация логгера
logger = logging.getLogger('PixelDeck.Navigation')

class NavigationController(QObject):
    """
    Контроллер навигации для управления слоями и фокусом в приложении.
    Интегрируется с основным окном и другими модулями через сигналы.
    """
    
    # Сигналы для взаимодействия с другими модулями
    layer_changed = pyqtSignal(int)  # Изменение текущего слоя
    focus_changed = pyqtSignal(QWidget)  # Изменение фокуса
    search_activated = pyqtSignal()  # Активация поиска
    
    # Константы для слоев
    MAIN_LAYER = 0
    SETTINGS_LAYER = 1
    SEARCH_LAYER = 2

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.current_layer = self.MAIN_LAYER
        self.current_focus = None
        self.focusable_widgets = []
        
        # Настройка путей (используем core.py для получения путей)
        from app.core import CONTENT_DIR, STYLES_DIR
        self.content_dir = Path(CONTENT_DIR)
        self.styles_dir = Path(STYLES_DIR)
        
        logger.info("Navigation controller initialized")

    def set_focusable_widgets(self, widgets):
        """Устанавливает список виджетов, которые могут получать фокус"""
        self.focusable_widgets = widgets
        if widgets:
            self.current_focus = widgets[0]
            self.update_focus_styles()
        logger.debug(f"Set focusable widgets: {len(widgets)} items")

    def switch_layer(self, new_layer):
        """Переключает между слоями приложения"""
        if new_layer == self.current_layer:
            return
            
        old_layer = self.current_layer
        self.current_layer = new_layer
        
        # Обработка перехода между слоями
        if new_layer == self.MAIN_LAYER:
            self._handle_main_layer_enter()
        elif new_layer == self.SETTINGS_LAYER:
            self._handle_settings_layer_enter()
        elif new_layer == self.SEARCH_LAYER:
            self._handle_search_layer_enter()
            
        self.layer_changed.emit(new_layer)
        logger.info(f"Layer changed from {old_layer} to {new_layer}")

    def _handle_main_layer_enter(self):
        """Обработчик входа в основной слой"""
        self.main_window.search_results_list.hide()
        self.main_window.search_field.clearFocus()
        self.clear_focus()
        self.main_window.setFocus()

    def _handle_settings_layer_enter(self):
        """Обработчик входа в слой настроек"""
        if self.focusable_widgets:
            self.set_focus(0)

    def _handle_search_layer_enter(self):
        """Обработчик входа в слой поиска"""
        self.main_window.search_field.setFocus()
        self.clear_focus()

    def move_focus(self, direction):
        """Перемещает фокус в указанном направлении"""
        if not self.focusable_widgets or self.current_layer != self.SETTINGS_LAYER:
            return
            
        current_index = self.focusable_widgets.index(self.current_focus) if self.current_focus else 0
        
        if direction == "right" and current_index < len(self.focusable_widgets) - 1:
            new_index = current_index + 1
        elif direction == "left" and current_index > 0:
            new_index = current_index - 1
        else:
            return
            
        self.set_focus(new_index)
        logger.debug(f"Focus moved {direction} to index {new_index}")

    def set_focus(self, index):
        """Устанавливает фокус на виджет с указанным индексом"""
        if 0 <= index < len(self.focusable_widgets):
            self.current_focus = self.focusable_widgets[index]
            self.current_focus.setFocus()
            self.focus_changed.emit(self.current_focus)
            self.update_focus_styles()
            
    def clear_focus(self):
        """Сбрасывает текущий фокус"""
        if self.current_focus:
            self.current_focus.clearFocus()
        self.current_focus = None
        self.update_focus_styles()
        
    def update_focus_styles(self):
        """Обновляет стили виджетов в зависимости от фокуса"""
        for widget in self.focusable_widgets:
            widget.setProperty("focused", widget == self.current_focus)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            
    def handle_key_event(self, event):
        """
        Обрабатывает нажатия клавиш и возвращает True, если событие было обработано.
        Если возвращает False, событие должно быть передано дальше.
        """
        key = event.key()
        
        # Глобальные горячие клавиши (работают в любом слое)
        if key == Qt.Key.Key_Escape:
            self.switch_layer(self.MAIN_LAYER)
            return True
            
        # Обработка в зависимости от текущего слоя
        if self.current_layer == self.MAIN_LAYER:
            return self._handle_main_layer_keys(key)
        elif self.current_layer == self.SETTINGS_LAYER:
            return self._handle_settings_layer_keys(key)
        elif self.current_layer == self.SEARCH_LAYER:
            return self._handle_search_layer_keys(key)
            
        return False

    def _handle_main_layer_keys(self, key):
        """Обработка клавиш в основном слое"""
        if key == Qt.Key.Key_Down:
            self.switch_layer(self.SETTINGS_LAYER)
            return True
        elif key == Qt.Key.Key_Y:
            self.switch_layer(self.SEARCH_LAYER)
            self.search_activated.emit()
            return True
        return False

    def _handle_settings_layer_keys(self, key):
        """Обработка клавиш в слое настроек"""
        if key == Qt.Key.Key_Up:
            self.switch_layer(self.MAIN_LAYER)
            return True
        elif key == Qt.Key.Key_Right:
            self.move_focus("right")
            return True
        elif key == Qt.Key.Key_Left:
            self.move_focus("left")
            return True
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_A):
            if self.current_focus:
                self.current_focus.click()
            return True
        elif key == Qt.Key.Key_B:
            self.switch_layer(self.MAIN_LAYER)
            return True
        return False

    def _handle_search_layer_keys(self, key):
        """Обработка клавиш в слое поиска"""
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.main_window.perform_search(self.main_window.search_field.text())
            return True
        elif key == Qt.Key.Key_B:
            self.switch_layer(self.MAIN_LAYER)
            return True
        return False

    def save_navigation_state(self):
        """Сохраняет текущее состояние навигации (для восстановления после перезапуска)"""
        # В будущем можно сохранять в app/settings.py
        pass

    def load_navigation_state(self):
        """Загружает сохраненное состояние навигации"""
        # В будущем можно загружать из app/settings.py
        pass
