from PyQt6.QtCore import QObject, pyqtSignal, Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QApplication, QPushButton, QDialog, QScrollArea,
    QWizard, QWizardPage, QLineEdit, QToolButton, QMenu
)
from pathlib import Path
from enum import Enum, auto
import base64
import sdl2
import sdl2.ext
import time
import logging

logger = logging.getLogger('ArcadeDeck.Navigation')

class NavigationLayer(Enum):
    MAIN = auto()
    SETTINGS = auto()
    SEARCH = auto()
    GAME_INFO = auto()
    DIALOG = auto()
    INSTALL = auto()
    SYSTEM_DIALOG = auto()

class SDLController(QObject):
    """Управление SDL2 геймпадом. Генерирует сигналы для навигации."""

    button_pressed = pyqtSignal(str)
    axis_moved = pyqtSignal(str)
    gamepad_connected_changed = pyqtSignal(bool)

    # Маппинг SDL кодов -> строковые имена
    _BUTTON_MAP = {
        sdl2.SDL_CONTROLLER_BUTTON_DPAD_UP: 'UP',
        sdl2.SDL_CONTROLLER_BUTTON_DPAD_DOWN: 'DOWN',
        sdl2.SDL_CONTROLLER_BUTTON_DPAD_LEFT: 'LEFT',
        sdl2.SDL_CONTROLLER_BUTTON_DPAD_RIGHT: 'RIGHT',
        sdl2.SDL_CONTROLLER_BUTTON_A: 'A',
        sdl2.SDL_CONTROLLER_BUTTON_B: 'B',
        sdl2.SDL_CONTROLLER_BUTTON_X: 'X',
        sdl2.SDL_CONTROLLER_BUTTON_Y: 'Y',
        sdl2.SDL_CONTROLLER_BUTTON_BACK: 'SELECT',
        sdl2.SDL_CONTROLLER_BUTTON_START: 'START'
    }

    # Обратный маппинг для HintManager
    REVERSE_BUTTON_MAP = {v: k for k, v in _BUTTON_MAP.items()}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initialized = False
        self._controller = None
        self._poll_timer = None
        self._axis_locked = False
        self._last_axis_direction = None
        self._axis_deadzone = 16000

    def init(self) -> bool:
        """Инициализация SDL и подключение контроллера"""
        if self._initialized:
            return True

        logger.info("🕹️ Инициализация SDL2 для геймпада...")
        if sdl2.SDL_Init(sdl2.SDL_INIT_GAMECONTROLLER) != 0:
            logger.warning(f"❌ Ошибка SDL2: {sdl2.SDL_GetError().decode()}")
            return False

        sdl2.SDL_StartTextInput()
        cnt = sdl2.SDL_NumJoysticks()
        logger.info(f"🔍 Найдено джойстиков: {cnt}")
        for i in range(cnt):
            if sdl2.SDL_IsGameController(i):
                self._controller = sdl2.SDL_GameControllerOpen(i)
                if self._controller:
                    name = sdl2.SDL_GameControllerName(self._controller).decode()
                    logger.info(f"🎮 Подключен контроллер: {name} (индекс {i})")
                    self._initialized = True
                    self.gamepad_connected_changed.emit(True)
                    break
        if not self._controller:
            logger.info("ℹ️ Геймпад не найден, используется клавиатура")
            self.gamepad_connected_changed.emit(False)
        return self._initialized

    def start_polling(self, interval_ms: int = 16):
        """Запуск цикла опроса событий SDL"""
        if self._poll_timer:
            return
        self._poll_timer = QTimer(self)
        self._poll_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._poll_timer.timeout.connect(self._poll_events)
        self._poll_timer.start(interval_ms)

    def stop_polling(self):
        """Остановка опроса"""
        if self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer = None

    def _poll_events(self):
        """Обработка событий SDL (вызывается по таймеру)"""
        if not self._initialized:
            return
        event = sdl2.SDL_Event()
        while sdl2.SDL_PollEvent(event):
            try:
                if event.type == sdl2.SDL_CONTROLLERBUTTONDOWN:
                    self._on_button(event.cbutton.button, pressed=True)
                elif event.type == sdl2.SDL_CONTROLLERBUTTONUP:
                    self._on_button(event.cbutton.button, pressed=False)
                elif event.type == sdl2.SDL_CONTROLLERAXISMOTION:
                    self._on_axis(event.caxis.axis, event.caxis.value)
                elif event.type == sdl2.SDL_CONTROLLERDEVICEADDED:
                    logger.info("🎮 Контроллер подключен")
                elif event.type == sdl2.SDL_CONTROLLERDEVICEREMOVED:
                    logger.info("🎮 Контроллер отключен")
            except Exception as e:
                logger.exception(f"SDL event error: {e}")

    def _on_button(self, sdl_button, pressed):
        """Обработка нажатия/отпускания кнопки"""
        if not pressed:
            return  # нас интересуют только нажатия
        button_name = self._BUTTON_MAP.get(sdl_button)
        if button_name:
            self.button_pressed.emit(button_name)

    def _on_axis(self, axis, value):
        """Обработка движения оси (стика)"""
        direction = None
        if axis == sdl2.SDL_CONTROLLER_AXIS_LEFTX:
            if value > self._axis_deadzone:
                direction = "RIGHT"
            elif value < -self._axis_deadzone:
                direction = "LEFT"
        elif axis == sdl2.SDL_CONTROLLER_AXIS_LEFTY:
            if value > self._axis_deadzone:
                direction = "DOWN"
            elif value < -self._axis_deadzone:
                direction = "UP"

        if abs(value) < self._axis_deadzone // 2:
            self._axis_locked = False
            self._last_axis_direction = None
            return

        if not direction:
            return

        if self._axis_locked and self._last_axis_direction == direction:
            return

        self._axis_locked = True
        self._last_axis_direction = direction
        if direction:
            logger.debug(f"SDL axis: {direction}")
            self.axis_moved.emit(direction)

    def cleanup(self):
        """Освобождение ресурсов SDL"""
        self.stop_polling()
        if self._controller:
            sdl2.SDL_GameControllerClose(self._controller)
        sdl2.SDL_Quit()
        self._initialized = False
        logger.info("SDL2 очищен")

class FocusManager(QObject):
    """Управление фокусом виджетов для навигации"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layer_widgets = {layer: [] for layer in NavigationLayer}
        self.focus_index = {layer: 0 for layer in NavigationLayer}

        # Параметры для 2D-навигации на MAIN слое
        self.main_header_len = 0
        self.main_tags_len = 0
        self.main_grid_cols = 0

    def register_widgets(self, layer: NavigationLayer, widgets: list):
        """Регистрирует виджеты для указанного слоя"""
        if not isinstance(layer, NavigationLayer):
            raise ValueError(f"Неверный слой навигации: {layer}")
        self.layer_widgets[layer] = []
        for w in widgets:
            try:
                w.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                # Сброс свойства focused (будет установлено позже)
                w.setProperty("focused", False)
                w.style().unpolish(w)
                w.style().polish(w)
                self.layer_widgets[layer].append(w)
            except Exception as e:
                logger.debug(f"⚠️ Не удалось инициализировать фокус для {w}: {e}")
        logger.info(f"📋 Зарегистрировано {len(self.layer_widgets[layer])} виджетов для слоя {layer.name}")

    def get_widgets(self, layer: NavigationLayer) -> list:
        return self.layer_widgets.get(layer)

    def get_focus_index(self, layer: NavigationLayer) -> int:
        return self.focus_index.get(layer, 0)

    def set_focus_index(self, layer: NavigationLayer, index: int):
        """Устанавливает индекс фокуса без применения к виджету"""
        if layer in self.focus_index:
            self.focus_index[layer] = index

    def clear_focus_properties(self, layer: NavigationLayer):
        """Сбрасывает свойство 'focused' на всех виджетах слоя (без вызова clearFocus)"""
        for w in self.layer_widgets.get(layer):
            try:
                w.setProperty("focused", False)
                w.style().unpolish(w)
                w.style().polish(w)
            except RuntimeError:
                continue

    def move_focus_linear(self, layer: NavigationLayer, direction: int) -> int:
        """Линейное перемещение фокуса (direction = -1 или 1) для слоёв, не MAIN"""
        widgets = self.layer_widgets.get(layer)
        if not widgets:
            return -1
        cur = self.focus_index.get(layer, 0)
        new = (cur + direction) % len(widgets)
        self.focus_index[layer] = new
        return new

    def navigate_main(self, direction: str) -> int:
        """2D-навигация по MAIN слою. Возвращает новый индекс или -1, если изменения не требуется"""
        widgets = self.layer_widgets.get(NavigationLayer.MAIN)
        if not widgets:
            return -1

        current_idx = self.focus_index.get(NavigationLayer.MAIN, 0)
        header_end = self.main_header_len
        tags_end = header_end + self.main_tags_len
        grid_start = tags_end
        num_widgets = len(widgets)

        # Определяем текущую группу
        if current_idx < header_end:
            group = 'header'
        elif current_idx < tags_end:
            group = 'tags'
            tags_idx = current_idx - header_end
        else:
            group = 'grid'
            grid_idx = current_idx - grid_start
            num_grid = num_widgets - grid_start
            if self.main_grid_cols == 0:
                return -1  # сетка не настроена
            num_rows = (num_grid + self.main_grid_cols - 1) // self.main_grid_cols
            current_col = grid_idx % self.main_grid_cols
            current_row = grid_idx // self.main_grid_cols

        new_idx = current_idx

        if direction == 'LEFT':
            if group == 'grid':
                if current_col > 0:
                    new_idx -= 1
                else:
                    new_idx += self.main_grid_cols - 1
                    if new_idx >= num_widgets:
                        new_idx = current_idx
            elif group == 'header':
                new_idx = (current_idx - 1) % header_end if header_end > 0 else current_idx
            elif group == 'tags':
                if self.main_tags_len > 0:
                    new_idx = header_end + ((tags_idx - 1) % self.main_tags_len)
        elif direction == 'RIGHT':
            if group == 'grid':
                if current_col < self.main_grid_cols - 1 and grid_idx + 1 < num_grid:
                    new_idx += 1
                else:
                    new_idx -= current_col
            elif group == 'header':
                new_idx = (current_idx + 1) % header_end if header_end > 0 else current_idx
            elif group == 'tags':
                if self.main_tags_len > 0:
                    new_idx = header_end + ((tags_idx + 1) % self.main_tags_len)
        elif direction == 'UP':
            if group == 'grid':
                if current_row > 0:
                    new_idx -= self.main_grid_cols
                else:
                    new_idx = header_end
            elif group == 'tags':
                if header_end > 0:
                    new_idx = min(1, header_end - 1)
            # header: остаёмся
        elif direction == 'DOWN':
            if group == 'grid':
                if current_row < num_rows - 1 and grid_idx + self.main_grid_cols < num_grid:
                    new_idx += self.main_grid_cols
            elif group == 'tags':
                if self.main_grid_cols > 0:
                    target_col = min(tags_idx, self.main_grid_cols - 1)
                    new_idx = grid_start + target_col
            elif group == 'header':
                new_idx = header_end

        if new_idx != current_idx and 0 <= new_idx < num_widgets:
            self.focus_index[NavigationLayer.MAIN] = new_idx
            return new_idx
        return -1


class HintManager:
    """Отвечает за отображение подсказок с иконками кнопок геймпада"""
    def __init__(self, icons_path: Path):
        self.icons_path = icons_path
        self.icon_cache = {}
        self.hint_widget = None
        # Берём маппинг из SDLController
        self.key_mapping = SDLController.REVERSE_BUTTON_MAP

    def set_hint_widget(self, widget):
        if widget is None:
            self.hint_widget = None
            return
        if not hasattr(widget, "setText"):
            raise ValueError("Виджет подсказок должен поддерживать setText()")
        self.hint_widget = widget

    def update_hints(self, current_layer, hint_overrides=None, navigation_locked=False):
        if not self.hint_widget:
            return

        if current_layer == NavigationLayer.SETTINGS and navigation_locked:
            base = "{UP}/{DOWN}: Навигация  |  {A}: Выбрать  |  {B}: Назад к вкладкам"
        elif hint_overrides and current_layer in hint_overrides:
            base = hint_overrides[current_layer]
        else:
            hints = {
                NavigationLayer.MAIN: "{LEFT}/{RIGHT}/{UP}/{DOWN} Навигация     {SELECT}  Настройки     {Y} Поиск     {A} Действие     {B} Выход",
                NavigationLayer.SETTINGS: "{UP}/{DOWN} Навигация     {RIGHT} Войти в настройки     {LEFT} Назад     {A} Действие     {SELECT}/{B} Назад",
                NavigationLayer.SEARCH: "{UP}/{DOWN} Навигация     {A} Выбор результата     {Y} Закрыть поиск",
                NavigationLayer.GAME_INFO: "{LEFT}/{RIGHT} Переключение кнопок     {A} Действие     {B} Назад",
                NavigationLayer.INSTALL: "{UP}/{DOWN} Выбор     {A} Действие     {B} Отмена",
                NavigationLayer.DIALOG: "{UP}/{DOWN} Выбор     {A} Действие     {B} Отмена",
            }
            base = hints.get(current_layer, "")

        formatted = self._format_hints_with_icons(base)
        formatted = formatted.replace("     ", "&nbsp;" * 12)
        html = f'<div style="padding: 8px 16px; font-size: 20px; text-align: center; white-space: nowrap;">{formatted}</div>'
        self.hint_widget.setText(f"<html><body style='margin:0;'>{html}</body></html>")

    def _get_button_icon(self, button_name, size=28):
        button_map = {
            'A': 'A.svg', 'B': 'B.svg', 'X': 'X.svg', 'Y': 'Y.svg',
            'UP': 'UP.svg', 'DOWN': 'DOWN.svg',
            'LEFT': 'LEFT.svg', 'RIGHT': 'RIGHT.svg',
            'SELECT': 'View.svg', 'START': 'Option.svg',
        }
        icon_file = button_map.get(button_name)
        if not icon_file:
            return button_name
        cache_key = f"{icon_file}_{size}"
        if cache_key in self.icon_cache:
            return self.icon_cache[cache_key]
        icon_path = self.icons_path / icon_file
        if not icon_path.exists():
            alt = self.icons_path.parent / icon_file
            if alt.exists():
                icon_path = alt
            else:
                logger.debug(f"⚠️ Иконка не найдена: {icon_file}")
                self.icon_cache[cache_key] = button_name
                return button_name
        try:
            with open(icon_path, 'rb') as f:
                svg_data = f.read()
            b64 = base64.b64encode(svg_data).decode('utf-8')
            html = f'<img src="data:image/svg+xml;base64,{b64}" style="width:{size}px; height:{size}px; vertical-align: middle; margin:0 6px 0 0;" />'
            self.icon_cache[cache_key] = html
            return html
        except Exception as e:
            logger.debug(f"⚠️ Ошибка загрузки иконки {icon_file}: {e}")
            return button_name

    def _format_hints_with_icons(self, text):
        for key in self.key_mapping.keys():
            placeholder = f"{{{key}}}"
            if placeholder in text:
                icon = self._get_button_icon(key)
                text = text.replace(placeholder, icon)
        arrow_map = {'←': 'LEFT', '→': 'RIGHT', '↑': 'UP', '↓': 'DOWN'}
        for arrow, key in arrow_map.items():
            if arrow in text:
                text = text.replace(arrow, self._get_button_icon(key))
        return text

class LayerManager(QObject):
    """Управление слоями навигации: переключение, маршрутизация, возврат на предыдущий слой"""
    layer_changed = pyqtSignal(NavigationLayer)

    def __init__(self, nav_controller, main_window):
        super().__init__()
        self.nav = nav_controller          # обратная ссылка на NavigationController
        self.main_window = main_window
        self._current_layer = NavigationLayer.MAIN
        self._previous_layer = None

    @property
    def current_layer(self) -> NavigationLayer:
        return self._current_layer

    @property
    def previous_layer(self) -> NavigationLayer | None:
        return self._previous_layer

    def switch_to(self, new_layer: NavigationLayer) -> None:
        if new_layer == self._current_layer:
            return
        logger.info(f"🔄 Переключение слоя: {self._current_layer.name} → {new_layer.name}")
        self._previous_layer = self._current_layer
        self.nav.clear_focus(self._current_layer)
        self._current_layer = new_layer

        # --- ДОБАВЛЯЕМ АКТИВАЦИЮ ОКНА ДЛЯ ДИАЛОГОВ ---
        if new_layer == NavigationLayer.DIALOG:
            # Ищем активный диалог среди управляемых окон
            for w in self.nav.managed_windows:
                if w.isVisible() and isinstance(w, QDialog):
                    w.activateWindow()
                    w.raise_()
                    w.setFocus()
                    logger.info(f"🔁 Активировано диалоговое окно: {w.__class__.__name__}")
                    break
        # -------------------------------------------

        widgets = self.nav.focus_manager.get_widgets(new_layer)
        if widgets:
            idx = min(self.nav.focus_manager.get_focus_index(new_layer), len(widgets) - 1)
            self.nav.set_focus(new_layer, idx)
        else:
            if QApplication.focusWidget():
                QApplication.focusWidget().clearFocus()
        self.layer_changed.emit(new_layer)
        self.nav.update_hints()
        if new_layer == NavigationLayer.SEARCH:
            self.nav.search_activated.emit()

    def route_navigation(self, direction: str) -> None:
        """Маршрутизирует нажатия D-pad/стика в зависимости от текущего слоя"""
        if self._current_layer == NavigationLayer.MAIN:
            self.nav._handle_main_navigation(direction)
        elif self._current_layer == NavigationLayer.SETTINGS:
            self.nav._handle_settings_navigation(direction)
        elif self._current_layer == NavigationLayer.GAME_INFO:
            self.nav._handle_game_info_navigation(direction)
        elif self._current_layer == NavigationLayer.INSTALL:
            self.nav._handle_install_navigation(direction)
        elif self._current_layer == NavigationLayer.DIALOG:
            self.nav._handle_dialog_navigation(direction)
        elif self._current_layer == NavigationLayer.SEARCH:
            self.nav._handle_search_navigation(direction)
        elif self._current_layer == NavigationLayer.SYSTEM_DIALOG:
            self.nav._handle_system_dialog_navigation(direction)

    def go_back(self) -> None:
        """Возврат на предыдущий слой (если есть) или на MAIN"""
        if self._previous_layer:
            self.switch_to(self._previous_layer)
        else:
            self.switch_to(NavigationLayer.MAIN)

class NavigationController(QObject):
    layer_changed = pyqtSignal(NavigationLayer)   # можно оставить, он будет переназначен
    focus_changed = pyqtSignal(QWidget)
    search_activated = pyqtSignal()
    button_pressed = pyqtSignal(str)

    def __init__(self, main_window, hint_overrides=None):

        super().__init__()
        self.main_window = main_window
        self.managed_windows = [main_window]
        self.dialog_menu = None
        self._input_blocked = False
        self._dialog_open = False
        self._current_dialog = None

        # Hint Manager
        icons_path = Path(__file__).parent / "ui_assets" / "icon" / "Steam Deck"
        self.hint_manager = HintManager(icons_path)
        self.hint_overrides = hint_overrides or {}

        self.focus_manager = FocusManager(self)
        self.layer_manager = LayerManager(self, main_window)
        self.layer_changed = self.layer_manager.layer_changed

        # Единый кулдаун для всех действий
        self._last_action_time = 0.0
        self._action_cooldown = 0.3  # секунд

        # Флаг подключения геймпада
        self.gamepad_connected = False

        # SDL Controller
        self.sdl = SDLController(self)
        self.sdl.init()
        self.sdl.start_polling()
        self.sdl.button_pressed.connect(self._on_sdl_button)
        self.sdl.axis_moved.connect(self._on_sdl_axis)
        self.sdl.gamepad_connected_changed.connect(self._on_gamepad_connected_changed)

        logger.info("✅ Навигационный контроллер инициализирован")

    def _on_gamepad_connected_changed(self, connected: bool):
        self.gamepad_connected = connected
        logger.info(f"🎮 Статус геймпада: {'подключён' if connected else 'отключён'}")

    def _on_dialog_finished(self, result):
        """Обработчик закрытия диалога"""
        if hasattr(self, '_current_dialog') and self._current_dialog:
            try:
                self._current_dialog.finished.disconnect(self._on_dialog_finished)
            except:
                pass

            self.remove_managed_window(self._current_dialog)
            self._current_dialog = None

        self.set_dialog_open(False)

        # Возврат на предыдущий слой
        if self.previous_layer and self.previous_layer != NavigationLayer.DIALOG:
            self.switch_layer(self.previous_layer)
        else:
            self.switch_layer(NavigationLayer.MAIN)

        # Очистка
        self.focus_manager.layer_widgets[NavigationLayer.DIALOG] = []
        self.focus_manager.focus_index[NavigationLayer.DIALOG] = 0

        self.update_hints()
        logger.info(f"Диалог закрыт, возврат к {self.current_layer.name}")

    def close_current_dialog(self) -> bool:
        """Закрывает текущий открытый диалог, если он есть."""
        if self._current_dialog and self._current_dialog.isVisible():
            self._current_dialog.close()
            return True
        return False

    @property
    def current_layer(self):
        return self.layer_manager.current_layer

    @property
    def previous_layer(self):
        return self.layer_manager.previous_layer

    # ---------- Слоты для сигналов SDLController ----------
    def _on_sdl_button(self, button_name: str):
        # Единый кулдаун
        now = time.time()
        if now - self._last_action_time < self._action_cooldown:
            return
        self._last_action_time = now

        if self._input_blocked and self.current_layer != NavigationLayer.DIALOG:
            return

        active_popup = QApplication.activePopupWidget()
        if active_popup and isinstance(active_popup, QMenu):
            self._handle_menu_navigation(button_name)
            return
        if active_popup:
            return

        if button_name in ('UP', 'DOWN', 'LEFT', 'RIGHT'):
            self._handle_dpad_navigation(button_name)
            return

        self._process_button_press(button_name)

    def _on_sdl_axis(self, direction: str):
        now = time.time()
        if now - self._last_action_time < self._action_cooldown:
            return
        self._last_action_time = now
        self.layer_manager.route_navigation(direction)

    def switch_layer(self, new_layer):
        self.layer_manager.switch_to(new_layer)

    def return_to_previous_layer(self):
        self.layer_manager.go_back()

    # ---------- Навигация D-pad (теперь принимает строку) ----------
    def _handle_dpad_navigation(self, direction: str):
        if direction not in ('UP', 'DOWN', 'LEFT', 'RIGHT'):
            return
        if self.current_layer == NavigationLayer.MAIN:
            self._handle_main_navigation(direction)
        else:
            self.layer_manager.route_navigation(direction)

    # ---------- Обработка глобальных кнопок (теперь строки) ----------
    def _process_button_press(self, button: str):

        if self.current_layer != NavigationLayer.DIALOG and self.input_blocked:
            return False

        if (self.current_layer == NavigationLayer.SETTINGS and
            hasattr(self.main_window, 'settings_page') and
            self.main_window.settings_page.navigation_locked):
            if button == 'B':
                return self.main_window.settings_page.navigate_left()
            elif button == 'A':
                return self.main_window.settings_page.activate_current()
            return True

        if self.current_layer == NavigationLayer.SYSTEM_DIALOG:
            if button == 'A':
                return self.activate_focused_widget()
            elif button == 'B':
                # Закрываем текущий SYSTEM_DIALOG
                active_dialog = QApplication.activeModalWidget()
                if active_dialog and isinstance(active_dialog, QDialog):
                    active_dialog.reject()   # или .close()
                else:
                    self._close_system_dialog()
                return True
            return True

        if self.current_layer == NavigationLayer.INSTALL:
            if button == 'A':
                return self.activate_focused_widget()
            elif button == 'B':
                return self._handle_back_action()
            return True

        if self._handle_global_buttons(button):
            return True
        if self._handle_layer_specific_actions(button):
            return True
        return False

    def _handle_global_buttons(self, button: str):
        if self.current_layer == NavigationLayer.DIALOG:
            if button == 'A':
                return self.activate_focused_widget()
            elif button == 'B':
                return self._handle_back_action()
            return False

        if button == 'SELECT':
            if self.current_layer != NavigationLayer.SETTINGS:
                self.switch_layer(NavigationLayer.SETTINGS)
            else:
                self.switch_layer(NavigationLayer.MAIN)
            return True
        if button == 'B':
            return self._handle_back_action()
        if button == 'Y':
            return self._handle_search_action()
        if button == 'A':
            return self._handle_confirm_action()
        return False

    def register_widgets(self, layer, widgets):
        self.focus_manager.register_widgets(layer, widgets)
        if self.current_layer == layer and widgets:
            self.set_focus(layer, 0)

    def set_focus(self, layer, index):
        if layer != self.current_layer:
            return
        widgets = self.focus_manager.get_widgets(layer)
        if not widgets or not (0 <= index < len(widgets)):
            return
        # Сброс стилей у всех виджетов слоя
        self.focus_manager.clear_focus_properties(layer)
        w = widgets[index]
        w.setProperty("focused", True)
        w.style().unpolish(w)
        w.style().polish(w)
        if isinstance(w, QLineEdit):
            w.setFocus(Qt.FocusReason.OtherFocusReason)
            w.deselect()
        else:
            w.setFocus(Qt.FocusReason.TabFocusReason)
        self.focus_manager.set_focus_index(layer, index)
        self.focus_changed.emit(w)
        logger.debug(f"🎯 Фокус установлен на индекс {index} в слое {layer.name}")
        if layer == NavigationLayer.MAIN:
            QTimer.singleShot(30, self._scroll_to_focused_tile)

    def clear_focus(self, layer):
        self.focus_manager.clear_focus_properties(layer)

    def move_focus(self, direction):
        if self.current_layer == NavigationLayer.MAIN:
            return
        new_idx = self.focus_manager.move_focus_linear(self.current_layer, direction)
        if new_idx >= 0:
            self.set_focus(self.current_layer, new_idx)

    @property
    def input_blocked(self):
        return self._input_blocked

    def set_dialog_open(self, is_open):
        old = self.input_blocked
        self._dialog_open = is_open
        if old != self.input_blocked:
            logger.info(f"💬 Диалог {'открыт' if is_open else 'закрыт'}, блокировка: {self.input_blocked}")

    def block_input(self, block=True):
        old = self.input_blocked
        self._input_blocked = block
        if old != self.input_blocked:
            logger.info(f"🔒 Ручная блокировка ввода: {block}")

    def _handle_menu_navigation(self, direction):
        menu = self.dialog_menu
        if not menu:
            return
        actions = [a for a in menu.actions() if not a.isSeparator() and a.isEnabled()]
        if not actions:
            return
        current = menu.activeAction()
        idx = 0 if current not in actions else actions.index(current)
        if direction in ("DOWN", "RIGHT"):
            idx = (idx + 1) % len(actions)
        elif direction in ("UP", "LEFT"):
            idx = (idx - 1) % len(actions)
        else:
            return
        menu.setActiveAction(actions[idx])

    def _close_system_dialog(self):
        """Закрывает текущий системный диалог (если есть)."""
        # Сначала проверяем сохранённый диалог
        if self._current_dialog and self._current_dialog.isVisible():
            self._current_dialog.close()
            return
        # Иначе ищем среди всех виджетов верхнего уровня
        for w in QApplication.topLevelWidgets():
            if isinstance(w, QDialog) and w.isVisible() and (w.isModal() or w.windowModality() != Qt.WindowModality.NonModal):
                w.close()
                break

    def _handle_main_navigation(self, direction: str):
        new_idx = self.focus_manager.navigate_main(direction)
        if new_idx >= 0:
            self.set_focus(NavigationLayer.MAIN, new_idx)

    def _handle_settings_navigation(self, direction):
        if direction in ('UP','DOWN','LEFT','RIGHT') and hasattr(self.main_window, 'settings_page'):
            sp = self.main_window.settings_page
            if direction == 'UP':
                return sp.navigate_up()
            elif direction == 'DOWN':
                return sp.navigate_down()
            elif direction == 'RIGHT':
                return sp.navigate_right()
            elif direction == 'LEFT':
                return sp.navigate_left()
        return False

    def _handle_game_info_navigation(self, direction):
        widgets = self.focus_manager.get_widgets(NavigationLayer.GAME_INFO)
        if not widgets:
            return
        cur = self.focus_manager.get_focus_index(NavigationLayer.GAME_INFO)
        if direction in ('LEFT','RIGHT'):
            new = (cur - 1) % len(widgets) if direction == 'LEFT' else (cur + 1) % len(widgets)
            self.set_focus(NavigationLayer.GAME_INFO, new)

    def _handle_install_navigation(self, direction):
        widgets = self.focus_manager.get_widgets(NavigationLayer.INSTALL)
        if not widgets:
            return
        cur = self.focus_manager.get_focus_index(NavigationLayer.INSTALL)
        if direction in ('LEFT','RIGHT','UP','DOWN'):
            new = (cur - 1) % len(widgets) if direction in ('LEFT','UP') else (cur + 1) % len(widgets)
            self.set_focus(NavigationLayer.INSTALL, new)

    def _handle_dialog_navigation(self, direction: str):
        """Простая линейная навигация для диалогов (2–4 кнопки)"""
        widgets = self.focus_manager.get_widgets(NavigationLayer.DIALOG)
        if not widgets:
            return

        cur = self.focus_manager.get_focus_index(NavigationLayer.DIALOG)
        if direction in ('LEFT', 'UP'):
            new_idx = (cur - 1) % len(widgets)
        else:  # RIGHT, DOWN
            new_idx = (cur + 1) % len(widgets)

        if new_idx != cur:
            self.set_focus(NavigationLayer.DIALOG, new_idx)

    def _handle_system_dialog_navigation(self, direction):
        widgets = self.focus_manager.get_widgets(NavigationLayer.SYSTEM_DIALOG)
        if not widgets:
            return
        cur = self.focus_manager.get_focus_index(NavigationLayer.SYSTEM_DIALOG)
        if direction in ('LEFT','RIGHT','UP','DOWN'):
            new = (cur - 1) % len(widgets) if direction in ('LEFT','UP') else (cur + 1) % len(widgets)
            self.set_focus(NavigationLayer.SYSTEM_DIALOG, new)

    def _handle_search_navigation(self, direction):
        widgets = self.focus_manager.get_widgets(NavigationLayer.SEARCH)
        if not widgets:
            return
        cur = self.focus_manager.get_focus_index(NavigationLayer.SEARCH)
        if cur == 0 and direction == 'DOWN' and len(widgets) > 1:
            self.set_focus(NavigationLayer.SEARCH, 1)
            self._scroll_search_to_focused(1)
        elif cur > 0:
            if direction == 'DOWN' and cur < len(widgets) - 1:
                self.set_focus(NavigationLayer.SEARCH, cur + 1)
                self._scroll_search_to_focused(cur + 1)
            elif direction == 'UP':
                if cur > 1:
                    self.set_focus(NavigationLayer.SEARCH, cur - 1)
                    self._scroll_search_to_focused(cur - 1)
                elif cur == 1:
                    self.set_focus(NavigationLayer.SEARCH, 0)

    def _scroll_search_to_focused(self, focus_idx):
        if not hasattr(self.main_window, 'library_page'):
            return
        library = self.main_window.library_page
        if not hasattr(library, '_search_overlay'):
            return
        search_overlay = library._search_overlay
        if not search_overlay or not search_overlay.isVisible():
            return
        widgets = self.focus_manager.get_widgets(NavigationLayer.SEARCH)
        if focus_idx < 0 or focus_idx >= len(widgets):
            return
        result_widget = widgets[focus_idx]
        QTimer.singleShot(10, lambda: self._ensure_search_visible(search_overlay, result_widget))

    def _ensure_search_visible(self, search_overlay, widget):
        try:
            scroll_area = None
            for child in search_overlay.findChildren(QScrollArea):
                if child.objectName() == "results_scroll" or hasattr(child, 'widget'):
                    scroll_area = child
                    break
            if not scroll_area:
                return
            container = scroll_area.widget()
            if not container:
                return
            widget_rect = widget.rect()
            widget_pos = widget.mapTo(container, widget_rect.topLeft())
            scroll_area.ensureVisible(
                widget_pos.x() + widget_rect.width() // 2,
                widget_pos.y() + widget_rect.height() // 2,
                widget_rect.width() // 2,
                widget_rect.height() // 2
            )
        except Exception as e:
            logger.debug(f"Ошибка прокрутки поиска: {e}")

    def _handle_search_action(self):
        if self.current_layer == NavigationLayer.SEARCH:
            self._close_search_overlay()
            return True
        elif self.current_layer == NavigationLayer.MAIN:
            self._open_search_overlay()
            return True
        return False

    def _open_search_overlay(self):
        if self.main_window and hasattr(self.main_window, 'library_page') and hasattr(self.main_window.library_page, 'show_search_overlay'):
            self.main_window.library_page.show_search_overlay()
            return True
        return False

    def _close_search_overlay(self):
        if self.main_window and hasattr(self.main_window, 'library_page') and hasattr(self.main_window.library_page, '_search_overlay'):
            overlay = self.main_window.library_page._search_overlay
            if overlay and overlay.isVisible():
                overlay.hide_overlay()
                return True
        return False

    def _handle_confirm_action(self):
        if self.current_layer == NavigationLayer.SEARCH:
            return self._activate_search_result()
        return self.activate_focused_widget()

    def _activate_search_result(self):
        idx = self.focus_manager.get_focus_index(NavigationLayer.SEARCH)
        widgets = self.focus_manager.get_widgets(NavigationLayer.SEARCH)
        if idx <= 0 or idx >= len(widgets):
            return False
        w = widgets[idx]
        if hasattr(w, 'activate') and callable(w.activate):
            w.activate()
            return True
        return False

    def _handle_layer_specific_actions(self, button: str):
        if self.current_layer in (NavigationLayer.MAIN, NavigationLayer.GAME_INFO) and button == 'A':
            return self.activate_focused_widget()
        return False

    def _handle_back_action(self):
        if self.current_layer == NavigationLayer.SEARCH:
            return False
        elif self.current_layer == NavigationLayer.SETTINGS:
            if hasattr(self.main_window, 'settings_page'):
                sp = self.main_window.settings_page
                if sp.navigation_locked or sp.in_details_mode:
                    return sp.navigate_left()
                else:
                    self.switch_layer(NavigationLayer.MAIN)
                    return True
        elif self.current_layer == NavigationLayer.GAME_INFO:
            self.switch_layer(NavigationLayer.MAIN)
            return True
        elif self.current_layer == NavigationLayer.DIALOG:
            return self.close_current_dialog()
        elif self.current_layer == NavigationLayer.INSTALL:
            return self.close_current_dialog()
        elif self.current_layer == NavigationLayer.MAIN:
            if hasattr(self.main_window, 'confirm_exit'):
                self.main_window.confirm_exit()
                return True
        return False

    # --------------------- Управление слоями и фокусом ---------------------

    def _scroll_to_focused_tile(self):
        idx = self.focus_manager.get_focus_index(NavigationLayer.MAIN)
        widgets = self.focus_manager.get_widgets(NavigationLayer.MAIN)
        if idx < 0 or idx >= len(widgets):
            return
        tile = widgets[idx]
        from app.modules.ui.game_library import GameTile
        if not isinstance(tile, GameTile):
            return
        container = tile.parent()
        scroll = container
        while scroll and not isinstance(scroll, QScrollArea):
            scroll = scroll.parent()
        if not scroll:
            return
        pos = tile.mapTo(container, tile.rect().topLeft())
        scroll.ensureVisible(pos.x() + tile.width()//2, pos.y() + tile.height()//2, tile.width()//2, tile.height()//2)

    def activate_focused_widget(self):
        layer = self.current_layer
        idx = self.focus_manager.get_focus_index(layer)
        widgets = self.focus_manager.get_widgets(layer)
        if not widgets or not (0 <= idx < len(widgets)):
            return False
        w = widgets[idx]

        # Блокируем ввод на 200 мс после активации, чтобы избежать эха
        self._input_blocked = True
        QTimer.singleShot(200, lambda: setattr(self, '_input_blocked', False))

        if isinstance(w, QPushButton):
            w.click()
            return True
        elif isinstance(w, QToolButton):
            if w.menu():
                w.showMenu()
                return True
            w.click()
            return True
        if hasattr(w, 'action') and callable(w.action):
            w.action()
            return True
        if hasattr(w, 'activate') and callable(w.activate):
            w.activate()
            return True
        w.setFocus(Qt.FocusReason.TabFocusReason)
        return False

    # --------------------- Подсказки ---------------------
    def set_hint_widget(self, widget):
        self.hint_manager.set_hint_widget(widget)

    def update_hints(self):
        navigation_locked = False
        if (self.current_layer == NavigationLayer.SETTINGS and
            hasattr(self.main_window, 'settings_page') and
            self.main_window.settings_page.navigation_locked):
            navigation_locked = True
        self.hint_manager.update_hints(self.current_layer, self.hint_overrides, navigation_locked)

    # --------------------- Вспомогательные методы ---------------------

    def add_managed_window(self, window):
        if window not in self.managed_windows:
            self.managed_windows.append(window)

    def remove_managed_window(self, window):
        if window in self.managed_windows:
            self.managed_windows.remove(window)

    def exit_dialog_mode(self):
        if self.current_layer == NavigationLayer.DIALOG:
            self.switch_layer(NavigationLayer.MAIN)

    def handle_key_event(self, event):
        """Обработка событий клавиатуры"""
        now = time.time()
        if now - self._last_action_time < self._action_cooldown:
            return False
        self._last_action_time = now

        if self.input_blocked and self.current_layer != NavigationLayer.DIALOG:
            return False

        # Если геймпад подключён, игнорируем клавиши навигации (кроме поля поиска)
        if self.gamepad_connected and self.current_layer != NavigationLayer.SEARCH:
            key = event.key()
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right,
                       Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
                return False

        key = event.key()
        modifiers = event.modifiers()

        # Навигация стрелками
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right):
            direction_map = {
                Qt.Key.Key_Up: 'UP',
                Qt.Key.Key_Down: 'DOWN',
                Qt.Key.Key_Left: 'LEFT',
                Qt.Key.Key_Right: 'RIGHT'
            }
            direction = direction_map[key]
            self._handle_dpad_navigation(direction)
            return True

        # Enter / A
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.current_layer == NavigationLayer.SEARCH:
                return self._activate_search_result()
            else:
                return self.activate_focused_widget()

        # Esc / B
        elif key == Qt.Key.Key_Escape:
            return self._handle_back_action()

        # Y / S поиск
        elif key in (Qt.Key.Key_Y, Qt.Key.Key_S):
            return self._handle_search_action()

        # Tab
        elif key == Qt.Key.Key_Tab:
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.move_focus(-1)
            else:
                self.move_focus(1)
            return True

        return False

    def block_gamepad_for_game(self, block: bool = True):
        """Полная блокировка/разблокировка геймпада при запуске игры"""
        if block:
            logger.info("🔒 ГЕЙМПАД ЗАБЛОКИРОВАН — игра запущена")
            self._input_blocked = True

            # Останавливаем polling
            if self.sdl and getattr(self.sdl, '_poll_timer', None):
                self.sdl.stop_polling()

            # Отключаем сигналы (с защитой)
            try:
                self.sdl.button_pressed.disconnect(self._on_sdl_button)
            except TypeError:
                pass  # уже отключен
            try:
                self.sdl.axis_moved.disconnect(self._on_sdl_axis)
            except TypeError:
                pass

        else:
            logger.info("🔓 ГЕЙМПАД РАЗБЛОКИРОВАН — игра завершена")
            self._input_blocked = False

            # Восстанавливаем polling
            if self.sdl and not getattr(self.sdl, '_poll_timer', None):
                self.sdl.start_polling(interval_ms=16)
            elif self.sdl and self.sdl._poll_timer and not self.sdl._poll_timer.isActive():
                self.sdl._poll_timer.start(16)

            # Переподключаем сигналы
            try:
                self.sdl.button_pressed.connect(self._on_sdl_button)
            except TypeError:
                pass  # уже подключен
            try:
                self.sdl.axis_moved.connect(self._on_sdl_axis)
            except TypeError:
                pass

            # Восстановление фокуса с небольшой задержкой
            QTimer.singleShot(1200, self._restore_focus_after_game)

    def _restore_focus_after_game(self):
        """Восстанавливаем фокус и слой после выхода из игры"""
        try:
            logger.info(f"🔄 Восстановление фокуса. Текущий слой: {self.current_layer.name}")

            # Принудительно активируем главное окно
            if self.main_window and not self.main_window.isActiveWindow():
                self.main_window.activateWindow()
                self.main_window.raise_()

            # Если были на странице игры — остаёмся там, иначе — в библиотеку
            if self.current_layer == NavigationLayer.GAME_INFO:
                self.set_focus(NavigationLayer.GAME_INFO, 0)
            else:
                self.switch_layer(NavigationLayer.MAIN)

            # Дополнительная страховка
            QTimer.singleShot(300, lambda: self.update_hints())

            logger.info("✅ Управление успешно восстановлено")

        except Exception as e:
            logger.error(f"❌ Ошибка восстановления фокуса: {e}", exc_info=True)


class WelcomeNavigationController(NavigationController):
    """Специализированный контроллер навигации для мастера приветствия"""
    
    def __init__(self, wizard):
        super().__init__(wizard)
        self.wizard = wizard
        self.layer_manager.switch_to(NavigationLayer.DIALOG)
        self.wizard_button_focus = 0  # 0 - кнопки страницы, 1 - кнопки мастера

    def _on_sdl_button(self, button_name: str):
        """Обработка кнопок для мастера"""
        if button_name == 'B':
            self._handle_back_action()
        else:
            super()._on_sdl_button(button_name)

    def _handle_dialog_navigation(self, direction):
        """Навигация в диалоге для мастера с группами фокуса"""
        widgets = self.focus_manager.get_widgets(NavigationLayer.DIALOG)
        if not widgets:
            return

        page_widgets = self.wizard.currentPage().page_widgets
        page_len = len(page_widgets)
        wizard_widgets = widgets[page_len:] if page_len < len(widgets) else []

        current_idx = self.focus_manager.get_focus_index(NavigationLayer.DIALOG)

        if self.wizard_button_focus == 0:  # Группа: кнопки страницы
            if page_len == 0:
                self.wizard_button_focus = 1
                return self._handle_dialog_navigation(direction)  # Перейти к wizard если нет page

            # Линейная навигация внутри группы
            if direction == 'LEFT' or direction == 'UP':
                new_idx = max(0, current_idx - 1)
            elif direction == 'RIGHT' or direction == 'DOWN':
                new_idx = min(page_len - 1, current_idx + 1)
            else:
                return

            # DOWN с последней: перейти к wizard
            if direction == 'DOWN' and current_idx == page_len - 1 and wizard_widgets:
                self.wizard_button_focus = 1
                new_idx = page_len  # Первая wizard button
            # UP с первой: остаться

        else:  # Группа: кнопки мастера
            if not wizard_widgets:
                self.wizard_button_focus = 0
                return self._handle_dialog_navigation(direction)

            local_idx = current_idx - page_len
            if direction == 'LEFT' or direction == 'DOWN':
                new_idx = max(0, local_idx - 1)
            elif direction == 'RIGHT' or direction == 'UP':
                new_idx = min(len(wizard_widgets) - 1, local_idx + 1)
            else:
                return

            # UP с первой: перейти к page
            if direction == 'UP' and local_idx == 0 and page_len > 0:
                self.wizard_button_focus = 0
                new_idx = page_len - 1  # Последняя page button
            # DOWN с последней: остаться

            new_idx = page_len + new_idx if self.wizard_button_focus == 1 else new_idx

        if 'new_idx' in locals() and new_idx != current_idx:
            self.set_focus(NavigationLayer.DIALOG, new_idx)

    def _handle_confirm_action(self):
        """Обработка A в мастере"""
        current_idx = self.focus_manager.get_focus_index(NavigationLayer.DIALOG)
        widgets = self.focus_manager.get_widgets(NavigationLayer.DIALOG)
        if not widgets or current_idx < 0 or current_idx >= len(widgets):
            return False

        widget = widgets[current_idx]
        if isinstance(widget, QPushButton):
            QTimer.singleShot(0, widget.click)
            return True
        return False

    def _handle_back_action(self):
        """Обработка B в мастере"""
        current_id = self.wizard.currentId()
        if current_id > 0:
            self.wizard.back()
            return True
        return False

    def handle_page_change(self, page_id):
        """Обработка смены страницы"""
        current_page = self.wizard.currentPage()
        page_len = len(current_page.page_widgets)
        self.wizard_button_focus = 0 if page_len > 0 else 1

        # Регистрация и фокус через initializePage (вызывается автоматически)
        # Но для верности: сброс и установка фокуса
        self.clear_focus(NavigationLayer.DIALOG)
        current_page.initializePage()  # Перерегистрирует и set_focus

    def update_hints(self):
        """Подсказки для мастера"""
        if not self.hint_widget:
            return
        text = "←/→:  | ↑/↓: Смена группы | A: Подтвердить | B: Назад"
        self.hint_widget.setText(text)
