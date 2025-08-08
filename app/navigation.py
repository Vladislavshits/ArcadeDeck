from PyQt6.QtCore import QObject, pyqtSignal, Qt, QTimer
from PyQt6.QtWidgets import QWidget, QApplication, QPushButton
import logging
from enum import Enum, auto
import sdl2
print(f"[DEBUG] Используется SDL2 версия: {sdl2.version.SDL_VERSIONNUM(2, 0, 0)}")

logger = logging.getLogger('PixelDeck.Navigation')

class NavigationLayer(Enum):
    MAIN = auto()
    SETTINGS = auto()
    SEARCH = auto()

class NavigationController(QObject):
    layer_changed = pyqtSignal(NavigationLayer)
    focus_changed = pyqtSignal(QWidget)
    search_activated = pyqtSignal()

    # Добавляем сигналы
    button_pressed = pyqtSignal(str)
    axis_moved = pyqtSignal(str, float)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.current_layer = NavigationLayer.MAIN
        self.previous_layer = None

        self.layer_widgets = {
            NavigationLayer.MAIN: [],
            NavigationLayer.SETTINGS: [],
            NavigationLayer.SEARCH: [],
        }

        self.focus_index = {
            NavigationLayer.MAIN: 0,
            NavigationLayer.SETTINGS: 0,
            NavigationLayer.SEARCH: 0,
        }

        self.key_mapping = {
            'UP': sdl2.SDL_CONTROLLER_BUTTON_DPAD_UP,
            'DOWN': sdl2.SDL_CONTROLLER_BUTTON_DPAD_DOWN,
            'LEFT': sdl2.SDL_CONTROLLER_BUTTON_DPAD_LEFT,
            'RIGHT': sdl2.SDL_CONTROLLER_BUTTON_DPAD_RIGHT,
            'A': sdl2.SDL_CONTROLLER_BUTTON_A,
            'B': sdl2.SDL_CONTROLLER_BUTTON_B,
            'Y': sdl2.SDL_CONTROLLER_BUTTON_Y,
            'X': sdl2.SDL_CONTROLLER_BUTTON_X,
            'SELECT': sdl2.SDL_CONTROLLER_BUTTON_BACK,
            'START': sdl2.SDL_CONTROLLER_BUTTON_START
        }

        self.button_state = {}
        self.sdl_initialized = False
        self.controller = None

        self.init_sdl2()

        self.timer = QTimer()
        self.timer.timeout.connect(self.poll_events)
        self.timer.start(16)

        logger.info("Navigation controller initialized")

    def init_sdl2(self):
        if self.sdl_initialized:
            return

        if sdl2.SDL_Init(sdl2.SDL_INIT_GAMECONTROLLER) != 0:
            print("SDL_Init Error:", sdl2.SDL_GetError().decode())
            return

        for i in range(sdl2.SDL_NumJoysticks()):
            if sdl2.SDL_IsGameController(i):
                self.controller = sdl2.SDL_GameControllerOpen(i)
                if self.controller:
                    print("[SDL2] Контроллер подключен")
                    self.sdl_initialized = True
                    break

        if not self.controller:
            print("[SDL2] Контроллер не найден")

    def poll_events(self):
        event = sdl2.SDL_Event()
        while sdl2.SDL_PollEvent(event):
            if event.type == sdl2.SDL_CONTROLLERBUTTONDOWN:
                button = event.cbutton.button
                self.button_state[button] = True
                self.handle_button_press(button)
            elif event.type == sdl2.SDL_CONTROLLERBUTTONUP:
                button = event.cbutton.button
                self.button_state[button] = False

    def handle_key_event(self, event):
        key = event.key()
        if key == Qt.Key.Key_Up:
            self.handle_button_press(self.key_mapping['UP'])
            return True
        elif key == Qt.Key.Key_Down:
            self.handle_button_press(self.key_mapping['DOWN'])
            return True
        elif key == Qt.Key.Key_Left:
            self.handle_button_press(self.key_mapping['LEFT'])
            return True
        elif key == Qt.Key.Key_Right:
            self.handle_button_press(self.key_mapping['RIGHT'])
            return True
        elif key == Qt.Key.Key_Return:
            self.handle_button_press(self.key_mapping['A'])
            return True
        elif key == Qt.Key.Key_Escape:
            self.handle_button_press(self.key_mapping['B'])
            return True
        return False

    def handle_button_press(self, button):
        logger.debug(f"Handling SDL2 button: {button} in layer {self.current_layer.name}")
        for name, sdl_code in self.key_mapping.items():
            if button == sdl_code:
                self.button_pressed.emit(name)
                break

        if button == self.key_mapping['B']:
            if self.current_layer in [NavigationLayer.SETTINGS, NavigationLayer.SEARCH]:
                self.switch_layer(NavigationLayer.MAIN)

        elif button == self.key_mapping['Y']:
            if self.current_layer != NavigationLayer.SEARCH:
                self.switch_layer(NavigationLayer.SEARCH)

        elif self.current_layer == NavigationLayer.MAIN:
            if button == self.key_mapping['DOWN']:
                self.switch_layer(NavigationLayer.SETTINGS)
            elif button == self.key_mapping['A']:
                self.activate_focused_widget()

        elif self.current_layer == NavigationLayer.SETTINGS:
            if button == self.key_mapping['UP']:
                self.switch_layer(NavigationLayer.MAIN)
            elif button == self.key_mapping['LEFT']:
                self.move_focus(-1)
            elif button == self.key_mapping['RIGHT']:
                self.move_focus(1)
            elif button == self.key_mapping['A']:
                self.activate_focused_widget()

    def register_widgets(self, layer, widgets):
        if not isinstance(layer, NavigationLayer):
            raise ValueError("Invalid navigation layer")
        self.layer_widgets[layer] = widgets
        logger.info(f"Registered {len(widgets)} widgets for {layer.name} layer")
        if widgets and self.current_layer == layer:
            self.set_focus(layer, 0)

    def return_to_previous_layer(self):
        if self.previous_layer:
            self.switch_layer(self.previous_layer)

    def switch_layer(self, new_layer):
        if new_layer == self.current_layer:
            return
        logger.info(f"Switching from {self.current_layer.name} to {new_layer.name}")
        self.clear_focus(self.current_layer)
        self.previous_layer = self.current_layer
        self.current_layer = new_layer
        widgets = self.layer_widgets.get(new_layer, [])
        if widgets:
            idx = self.focus_index[new_layer]
            if idx >= len(widgets):
                idx = 0
            self.set_focus(new_layer, idx)
        if new_layer == NavigationLayer.SEARCH:
            self.search_activated.emit()
        self.layer_changed.emit(new_layer)

    def set_focus(self, layer, index):
        if layer != self.current_layer:
            logger.warning(f"Attempt to set focus on inactive layer: {layer.name}")
            return
        widgets = self.layer_widgets.get(layer, [])
        if not widgets:
            return
        if index < 0 or index >= len(widgets):
            logger.error(f"Invalid focus index: {index} for layer {layer.name}")
            return
        for widget in widgets:
            widget.setProperty("focused", False)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        widget = widgets[index]
        widget.setProperty("focused", True)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.setFocus(Qt.FocusReason.TabFocusReason)
        self.focus_index[layer] = index
        self.focus_changed.emit(widget)
        logger.debug(f"Focus set to index {index} on {layer.name} layer")

    def clear_focus(self, layer):
        widgets = self.layer_widgets.get(layer, [])
        for widget in widgets:
            widget.setProperty("focused", False)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.clearFocus()

    def move_focus(self, direction):
        if not (-1 <= direction <= 1):
            raise ValueError("Direction must be -1 or 1")
        layer = self.current_layer
        widgets = self.layer_widgets.get(layer, [])
        if not widgets:
            return
        current_idx = self.focus_index[layer]
        new_idx = current_idx + direction
        if new_idx < 0:
            new_idx = len(widgets) - 1
        elif new_idx >= len(widgets):
            new_idx = 0
        self.set_focus(layer, new_idx)

    def activate_focused_widget(self):
        layer = self.current_layer
        idx = self.focus_index.get(layer, 0)
        widgets = self.layer_widgets.get(layer, [])
        if not widgets or idx < 0 or idx >= len(widgets):
            logger.warning("Nothing to activate")
            return
        widget = widgets[idx]
        if isinstance(widget, QPushButton):
            logger.debug(f"Activating button: {widget.text()}")
            QTimer.singleShot(0, widget.click)
            return
        if hasattr(widget, 'action') and callable(widget.action):
            logger.debug(f"Activating custom action on widget: {widget}")
            widget.action()
            return
        logger.debug(f"Setting focus to widget: {widget}")
        widget.setFocus(Qt.FocusReason.TabFocusReason)