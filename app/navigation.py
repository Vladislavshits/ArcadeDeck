from PyQt6.QtCore import QObject, pyqtSignal, Qt, QTimer
from PyQt6.QtWidgets import QWidget, QApplication, QPushButton
import logging
from enum import Enum, auto

logger = logging.getLogger('PixelDeck.Navigation')

class NavigationLayer(Enum):
    """Перечисление слоев навигации"""
    MAIN = auto()        # Главный слой с играми
    SETTINGS = auto()    # Слой настроек
    SEARCH = auto()      # Слой поиска (поверх всех)

class NavigationController(QObject):
    """Контроллер навигации для управления слоями и фокусом"""
    
    # Сигналы
    layer_changed = pyqtSignal(NavigationLayer)  # Изменение текущего слоя
    focus_changed = pyqtSignal(QWidget)          # Изменение фокусированного виджета
    search_activated = pyqtSignal()              # Активация поиска
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window  # Ссылка на главное окно
        self.current_layer = NavigationLayer.MAIN  # Текущий слой по умолчанию
        
        # Словари для хранения элементов управления по слоям
        # Формат: {слой: [список виджетов]}
        self.layer_widgets = {
            NavigationLayer.MAIN: [],
            NavigationLayer.SETTINGS: [],
            NavigationLayer.SEARCH: []
        }
        
        # Индексы фокуса для каждого слоя
        self.focus_index = {
            NavigationLayer.MAIN: 0,
            NavigationLayer.SETTINGS: 0,
            NavigationLayer.SEARCH: 0
        }
        
        # Обновленный маппинг клавиш
        self.key_mapping = {
            'UP': Qt.Key.Key_Up,
            'DOWN': Qt.Key.Key_Down,
            'LEFT': Qt.Key.Key_Left,
            'RIGHT': Qt.Key.Key_Right,
            'A': Qt.Key.Key_Return,      # Основная активация
            'B': Qt.Key.Key_Escape,      # Назад/отмена
            'Y': Qt.Key.Key_Space,       # Поиск
            'X': Qt.Key.Key_X,           # Доп. функция
            'SELECT': Qt.Key.Key_S,      # Специальные действия
            'START': Qt.Key.Key_Enter    # Запуск игры
        }
        
        logger.info("Navigation controller initialized")

    def register_widgets(self, layer, widgets):
        """
        Регистрация виджетов для слоя
        :param layer: Слой (из NavigationLayer)
        :param widgets: Список виджетов для управления
        """
        if not isinstance(layer, NavigationLayer):
            raise ValueError("Invalid navigation layer")
        
        self.layer_widgets[layer] = widgets
        logger.info(f"Registered {len(widgets)} widgets for {layer.name} layer")
        
        # Установка начального фокуса
        if widgets and self.current_layer == layer:
            self.set_focus(layer, 0)

    def switch_layer(self, new_layer):
        """
        Переключение между слоями
        :param new_layer: Новый активный слой
        """
        if new_layer == self.current_layer:
            return
            
        logger.info(f"Switching from {self.current_layer.name} to {new_layer.name}")
        
        # Очищаем фокус со старого слоя
        self.clear_focus(self.current_layer)
        
        # Устанавливаем новый слой
        self.current_layer = new_layer
        
        # Устанавливаем фокус на первый элемент нового слоя
        widgets = self.layer_widgets.get(new_layer, [])
        if widgets:
            idx = self.focus_index[new_layer]
            if idx >= len(widgets):
                idx = 0
            self.set_focus(new_layer, idx)
        
        # Специальная обработка для слоя поиска
        if new_layer == NavigationLayer.SEARCH:
            self.search_activated.emit()
        
        # Сигнализируем о смене слоя
        self.layer_changed.emit(new_layer)

    def set_focus(self, layer, index):
        """
        Установка фокуса на конкретный виджет в слое
        :param layer: Слой
        :param index: Индекс виджета в слое
        """
        if layer != self.current_layer:
            logger.warning(f"Attempt to set focus on inactive layer: {layer.name}")
            return
            
        widgets = self.layer_widgets.get(layer, [])
        if not widgets:
            return
            
        if index < 0 or index >= len(widgets):
            logger.error(f"Invalid focus index: {index} for layer {layer.name}")
            return
            
        # Снимаем фокус со всех виджетов слоя
        for widget in widgets:
            widget.setProperty("focused", False)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        
        # Устанавливаем фокус на выбранный виджет
        widget = widgets[index]
        widget.setProperty("focused", True)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.setFocus(Qt.FocusReason.TabFocusReason)
        
        # Сохраняем индекс
        self.focus_index[layer] = index
        self.focus_changed.emit(widget)
        
        logger.debug(f"Focus set to index {index} on {layer.name} layer")

    def clear_focus(self, layer):
        """Очистка фокуса для всех виджетов слоя"""
        widgets = self.layer_widgets.get(layer, [])
        for widget in widgets:
            widget.setProperty("focused", False)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.clearFocus()

    def move_focus(self, direction):
        """
        Перемещение фокуса в указанном направлении
        :param direction: Направление (-1 = влево/вверх, 1 = вправо/вниз)
        """
        if not (-1 <= direction <= 1):
            raise ValueError("Direction must be -1 or 1")
            
        layer = self.current_layer
        widgets = self.layer_widgets.get(layer, [])
        if not widgets:
            return
            
        current_idx = self.focus_index[layer]
        new_idx = current_idx + direction
        
        # Обработка границ
        if new_idx < 0:
            new_idx = len(widgets) - 1
        elif new_idx >= len(widgets):
            new_idx = 0
            
        self.set_focus(layer, new_idx)

    def handle_key_event(self, event):
        """
        Обработка событий клавиатуры/геймпада
        :param event: Событие клавиши
        :return: True если событие обработано, иначе False
        """
        key = event.key()
        logger.debug(f"Handling key: {key} in layer {self.current_layer.name}")
        
        # Обработка глобальных действий
        if key == self.key_mapping['B']:  # Кнопка B - Назад
            if self.current_layer == NavigationLayer.SETTINGS:
                self.switch_layer(NavigationLayer.MAIN)
                return True
            elif self.current_layer == NavigationLayer.SEARCH:
                self.switch_layer(NavigationLayer.MAIN)
                return True
                
        elif key == self.key_mapping['Y']:  # Кнопка Y - Поиск
            if self.current_layer != NavigationLayer.SEARCH:
                self.switch_layer(NavigationLayer.SEARCH)
                return True
                
        # Обработка действий по слоям
        if self.current_layer == NavigationLayer.MAIN:
            if key == self.key_mapping['DOWN']:
                self.switch_layer(NavigationLayer.SETTINGS)
                return True
            elif key == self.key_mapping['A']:
                self.activate_focused_widget()
                return True
                
        elif self.current_layer == NavigationLayer.SETTINGS:
            if key == self.key_mapping['UP']:
                self.switch_layer(NavigationLayer.MAIN)
                return True
            elif key == self.key_mapping['LEFT']:
                self.move_focus(-1)
                return True
            elif key == self.key_mapping['RIGHT']:
                self.move_focus(1)
                return True
            elif key == self.key_mapping['A']:
                self.activate_focused_widget()
                return True
                
        elif self.current_layer == NavigationLayer.SEARCH:
            # Здесь может быть ваша обработка поиска
            # Например, передача событий в поле поиска
            pass
            
        return False

    def activate_focused_widget(self):
        """Активация текущего сфокусированного виджета"""
        layer = self.current_layer
        widgets = self.layer_widgets.get(layer, [])
        if not widgets:
            return
            
        idx = self.focus_index[layer]
        if 0 <= idx < len(widgets):
            widget = widgets[idx]
            
            # Для кнопок - эмулируем клик
            if isinstance(widget, QPushButton):
                logger.debug(f"Activating button: {widget.text()}")
                QTimer.singleShot(0, widget.click)
            # Для других виджетов - активируем их стандартное действие
            else:
                logger.debug(f"Activating widget: {widget}")
                widget.setFocus(Qt.FocusReason.TabFocusReason)

            if hasattr(widget, 'activated') and callable(widget.activated):
                logger.debug(f"Activating widget: {widget}")
                widget.activated()
