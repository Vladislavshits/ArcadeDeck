from PyQt6.QtCore import QObject, pyqtSignal, Qt, QTimer
from PyQt6.QtWidgets import QWidget, QApplication, QPushButton
import logging
from enum import Enum, auto
import sdl2
import sdl2.ext

logger = logging.getLogger('ArcadeDeck.Navigation')

class NavigationLayer(Enum):
    """Слои навигации приложения"""
    MAIN = auto()
    SETTINGS = auto()
    SEARCH = auto()
    GAME_INFO = auto()

class NavigationController(QObject):
    """
    Централизованный контроллер навигации для ArcadeDeck
    Обеспечивает единообразную навигацию между всеми экранами
    """

    # Сигналы
    layer_changed = pyqtSignal(NavigationLayer)
    focus_changed = pyqtSignal(QWidget)
    search_activated = pyqtSignal()
    button_pressed = pyqtSignal(str)
    axis_moved = pyqtSignal(str, float)

    def __init__(self, main_window, hint_overrides=None):
        super().__init__()
        self.main_window = main_window
        self.current_layer = NavigationLayer.MAIN
        self.previous_layer = None
        self._active = True
        self._input_blocked = False  # 🔥 НОВЫЙ ФЛАГ: блокировка ввода

        # Инициализация структур данных
        self.layer_widgets = {
            NavigationLayer.MAIN: [],
            NavigationLayer.SETTINGS: [],
            NavigationLayer.SEARCH: [],
            NavigationLayer.GAME_INFO: [],
        }

        self.focus_index = {
            NavigationLayer.MAIN: 0,
            NavigationLayer.SETTINGS: 0,
            NavigationLayer.SEARCH: 0,
            NavigationLayer.GAME_INFO: 0,
        }

        # Маппинг кнопок геймпада
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
        self.hint_widget = None
        self.hint_overrides = hint_overrides or {}

        # Инициализация
        self._init_sdl2()
        self._start_event_polling()

        logger.info("✅ Навигационный контроллер инициализирован")

    # ==================== ИНИЦИАЛИЗАЦИЯ ====================

    def _init_sdl2(self):
        """Инициализация SDL2 для работы с геймпадом"""
        if self.sdl_initialized:
            return

        logger.info("🕹️ Инициализация SDL2 для геймпада...")

        # 🔥 ВАЖНО: Инициализируем ТОЛЬКО геймпад, не всю SDL
        if sdl2.SDL_Init(sdl2.SDL_INIT_GAMECONTROLLER) != 0:
            error_msg = sdl2.SDL_GetError().decode()
            logger.warning(f"❌ Ошибка инициализации SDL2: {error_msg}")
            return

        # Включаем опрос событий (это важно!)
        sdl2.SDL_StartTextInput()

        # Поиск подключенных контроллеров
        controller_count = sdl2.SDL_NumJoysticks()
        logger.info(f"🔍 Найдено джойстиков: {controller_count}")

        for i in range(controller_count):
            if sdl2.SDL_IsGameController(i):
                self.controller = sdl2.SDL_GameControllerOpen(i)
                if self.controller:
                    name = sdl2.SDL_GameControllerName(self.controller).decode()
                    logger.info(f"🎮 Подключен контроллер: {name} (индекс {i})")
                    self.sdl_initialized = True
                    break

        if not self.controller:
            logger.info("ℹ️ Геймпад не найден, используется клавиатурная навигация")

    def _start_event_polling(self):
        """Запуск опроса событий геймпада"""
        self.timer = QTimer()
        self.timer.timeout.connect(self._poll_controller_events)
        self.timer.start(16)  # ~60 FPS
        logger.debug("⏰ Таймер опроса геймпада запущен")

    # ==================== ОБРАБОТКА СОБЫТИЙ ====================

    def set_active(self, active):
        """Включает/выключает обработку ввода"""
        self._active = active
        logger.debug(f"Навигационный контроллер {'активен' if active else 'неактивен'}")

    def block_input(self, blocked):
        """🔥 НОВЫЙ МЕТОД: Блокирует весь ввод (для запуска игр)"""
        self._input_blocked = blocked
        logger.info(f"🎮 Ввод геймпада {'заблокирован' if blocked else 'разблокирован'}")

    def _is_input_allowed(self):
        """🔥 ВАЖНО: Проверяет, разрешен ли ввод в текущий момент"""
        # 1. Проверяем глобальную блокировку (для запуска игр)
        if self._input_blocked:
            return False

        # 2. Проверяем активность контроллера
        if not self._active:
            return False

        # 3. Проверяем, активно ли приложение
        if not self._is_app_active():
            return False

        return True

    def _is_app_active(self):
        """Проверяет, активно ли приложение и в фокусе"""
        if not self.main_window or not self.main_window.isVisible():
            return False

        # Проверяем, является ли окно активным
        if not self.main_window.isActiveWindow():
            return False

        # Дополнительная проверка для Qt
        app = QApplication.instance()
        if app and app.activeWindow() != self.main_window:
            return False

        return True

    def _poll_controller_events(self):
        """Опрос событий геймпада через SDL2"""
        # 🔥 ВАЖНО: Проверяем разрешение на ввод ПЕРЕД обработкой
        if not self._is_input_allowed():
            return

        event = sdl2.SDL_Event()
        while sdl2.SDL_PollEvent(event):
            if event.type == sdl2.SDL_CONTROLLERBUTTONDOWN:
                self._handle_controller_button(event.cbutton.button, True)
            elif event.type == sdl2.SDL_CONTROLLERBUTTONUP:
                self._handle_controller_button(event.cbutton.button, False)
            elif event.type == sdl2.SDL_CONTROLLERAXISMOTION:
                self._handle_controller_axis(event.caxis.axis, event.caxis.value)

    def _handle_controller_button(self, button, pressed):
        """Обработка нажатия/отпускания кнопки геймпада"""
        # 🔥 Двойная проверка
        if not self._is_input_allowed():
            return

        self.button_state[button] = pressed
        if pressed:
            logger.debug(f"🎮 Кнопка нажата: {button}")
            self._process_button_press(button)

    def _handle_controller_axis(self, axis, value):
        """Обработка движения осей геймпада"""
        # 🔥 Двойная проверка
        if not self._is_input_allowed():
            return

        try:
            normalized = value / 32767.0 if value >= 0 else value / 32768.0
        except Exception as e:
            logger.warning(f"⚠️ Ошибка нормализации оси: {e}")
            normalized = float(value)

        axis_name = None
        if axis == sdl2.SDL_CONTROLLER_AXIS_LEFTX:
            axis_name = 'LEFT_X'
        elif axis == sdl2.SDL_CONTROLLER_AXIS_LEFTY:
            axis_name = 'LEFT_Y'
        elif axis == sdl2.SDL_CONTROLLER_AXIS_RIGHTX:
            axis_name = 'RIGHT_X'
        elif axis == sdl2.SDL_CONTROLLER_AXIS_RIGHTY:
            axis_name = 'RIGHT_Y'

        if axis_name:
            self.axis_moved.emit(axis_name, normalized)

    def handle_key_event(self, event):
        """Обработка событий клавиатуры (для отладки)"""
        # 🔥 Проверяем разрешение на ввод
        if not self._is_input_allowed():
            return False

        key_map = {
            Qt.Key.Key_Up: 'UP',
            Qt.Key.Key_Down: 'DOWN',
            Qt.Key.Key_Left: 'LEFT',
            Qt.Key.Key_Right: 'RIGHT',
            Qt.Key.Key_Return: 'A',
            Qt.Key.Key_Escape: 'B',
            Qt.Key.Key_A: 'A',
            Qt.Key.Key_B: 'B',
            Qt.Key.Key_Y: 'Y',
            Qt.Key.Key_X: 'X'
        }

        button_name = key_map.get(event.key())
        if button_name:
            logger.debug(f"⌨️ Клавиша преобразована в: {button_name}")
            return self._process_button_press(button_name)

        return False

    # ==================== ОСНОВНАЯ ЛОГИКА ОБРАБОТКИ ====================

    def _process_button_press(self, button):
        """
        ГЛАВНЫЙ обработчик нажатий кнопок
        """
        # 🔥 ФИНАЛЬНАЯ проверка
        if not self._is_input_allowed():
            return False

        logger.debug(f"🔄 Обработка кнопки {button} в слое {self.current_layer.name}")

        # === 1. СПЕЦИАЛЬНЫЕ РЕЖИМЫ (высший приоритет) ===
        if self._handle_special_modes(button):
            return True

        # === 2. ГЛОБАЛЬНЫЕ СИГНАЛЫ (для статистики и мониторинга) ===
        self._emit_global_signals(button)

        # === 3. ОБРАБОТКА ПО СЛОЯМ (основная логика) ===
        if self._handle_layer_specific_actions(button):
            return True

        # === 4. ГЛОБАЛЬНЫЕ КНОПКИ (универсальные действия) ===
        if self._handle_global_buttons(button):
            return True

        logger.debug(f"➡️ Кнопка {button} не обработана в текущем контексте")
        return False

    def _handle_special_modes(self, button):
        """1. Обработка специальных режимов (поиск, диалоги)"""
        # Режим поиска - блокирует все кроме BACK
        if self.current_layer == NavigationLayer.SEARCH:
            if button == self.key_mapping['B']:
                logger.info("🔍 Выход из режима поиска")
                self.switch_layer(NavigationLayer.MAIN)
                return True
            # Все остальные кнопки блокируются в поиске
            logger.debug("🚫 Действие заблокировано в режиме поиска")
            return True

        return False

    def _emit_global_signals(self, button):
        """2. Глобальные сигналы для статистики"""
        for name, sdl_code in self.key_mapping.items():
            if button == sdl_code:
                try:
                    self.button_pressed.emit(name)
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки сигнала {name}: {e}")
                break

    def _handle_layer_specific_actions(self, button):
        """3. Обработка действий, специфичных для каждого слоя"""
        layer_handlers = {
            NavigationLayer.MAIN: self._handle_main_layer,
            NavigationLayer.SETTINGS: self._handle_settings_layer,
            NavigationLayer.GAME_INFO: self._handle_game_info_layer,
        }

        handler = layer_handlers.get(self.current_layer)
        if handler and handler(button):
            return True

        return False

    def _handle_global_buttons(self, button):
        """4. Обработка глобальных кнопок (работают везде)"""
        # === КНОПКА B (НАЗАД) - ЕДИНСТВЕННЫЙ обработчик ===
        if button == self.key_mapping['B']:
            return self._handle_back_action()

        # === КНОПКА SELECT (переключение настроек) ===
        if button == self.key_mapping['SELECT']:
            logger.info("⚙️ Переключение настроек")
            self.main_window.toggle_settings()
            return True

        # === КНОПКА Y (поиск) - только в главном меню ===
        if button == self.key_mapping['Y'] and self.current_layer == NavigationLayer.MAIN:
            logger.info("🔍 Активация поиска")
            self.switch_layer(NavigationLayer.SEARCH)
            return True

        return False

    # ==================== ОБРАБОТЧИКИ СЛОЕВ ====================

    def _handle_main_layer(self, button):
        """Обработка главного меню"""
        if button == self.key_mapping['DOWN']:
            logger.info("⬇️ Переход в настройки")
            self.switch_layer(NavigationLayer.SETTINGS)
            return True
        elif button == self.key_mapping['A']:
            logger.info("🎮 Запуск выбранной игры")
            self.activate_focused_widget()
            return True

        return False

    def _handle_settings_layer(self, button):
        """Обработка экрана настроек"""
        settings_page = self.main_window.settings_page

        if button == self.key_mapping['UP']:
            return settings_page.navigate_up()
        elif button == self.key_mapping['DOWN']:
            return settings_page.navigate_down()
        elif button == self.key_mapping['RIGHT']:
            return settings_page.navigate_right()
        elif button == self.key_mapping['LEFT']:
            return settings_page.navigate_left()
        elif button == self.key_mapping['A']:
            return settings_page.activate_current()

        return False

    def _handle_game_info_layer(self, button):
        """Обработка информации об игре"""
        widgets = self.layer_widgets.get(NavigationLayer.GAME_INFO, [])
        if not widgets:
            return False

        current_idx = self.focus_index[NavigationLayer.GAME_INFO]

        if button == self.key_mapping['LEFT']:
            new_idx = (current_idx - 1) % len(widgets)
            self.set_focus(NavigationLayer.GAME_INFO, new_idx)
            return True
        elif button == self.key_mapping['RIGHT']:
            new_idx = (current_idx + 1) % len(widgets)
            self.set_focus(NavigationLayer.GAME_INFO, new_idx)
            return True
        elif button == self.key_mapping['A']:
            self.activate_focused_widget()
            return True

        return False

    # ==================== ОБРАБОТКА КНОПКИ BACK ====================

    def _handle_back_action(self):
        """
        ЕДИНСТВЕННЫЙ обработчик кнопки BACK
        Исключает любые дублирования!
        """
        logger.info(f"🔙 Обработка BACK в слое {self.current_layer.name}")

        back_handlers = {
            NavigationLayer.MAIN: self._back_from_main,
            NavigationLayer.SETTINGS: self._back_from_settings,
            NavigationLayer.GAME_INFO: self._back_from_game_info,
            NavigationLayer.SEARCH: self._back_from_search,
        }

        handler = back_handlers.get(self.current_layer)
        if handler:
            return handler()

        logger.warning(f"⚠️ Неизвестный слой для BACK: {self.current_layer}")
        return False

    def _back_from_main(self):
        """BACK в главном меню = выход из приложения"""
        logger.info("🚪 Запрос выхода из приложения")
        self.main_window.confirm_exit()
        return True

    def _back_from_settings(self):
        """BACK в настройках = возврат в главное меню"""
        logger.info("🏠 Возврат из настроек в главное меню")
        self.switch_layer(NavigationLayer.MAIN)
        return True

    def _back_from_game_info(self):
        """BACK в информации об игре = возврат в библиотеку"""
        logger.info("📚 Возврат из информации об игре в библиотеку")
        self.switch_layer(NavigationLayer.MAIN)
        return True

    def _back_from_search(self):
        """BACK в поиске = возврат в главное меню"""
        logger.info("🔍 Закрытие поиска, возврат в главное меню")
        self.switch_layer(NavigationLayer.MAIN)
        return True

    # ==================== УПРАВЛЕНИЕ СЛОЯМИ И ФОКУСОМ ====================

    def switch_layer(self, new_layer):
        """Переключение между слоями интерфейса"""
        if new_layer == self.current_layer:
            return

        logger.info(f"🔄 Переключение слоя: {self.current_layer.name} → {new_layer.name}")

        # Сохраняем предыдущий слой
        self.previous_layer = self.current_layer

        # Очищаем фокус текущего слоя
        self.clear_focus(self.current_layer)

        # Устанавливаем новый слой
        self.current_layer = new_layer
        widgets = self.layer_widgets.get(new_layer, [])

        # Устанавливаем фокус (кроме режима поиска)
        if widgets and new_layer != NavigationLayer.SEARCH:
            idx = min(self.focus_index[new_layer], len(widgets) - 1)
            self.set_focus(new_layer, idx)
        else:
            # Снимаем фокус если нет виджетов или это поиск
            if QApplication.focusWidget():
                QApplication.focusWidget().clearFocus()

        # Сигналы и обновления
        if new_layer == NavigationLayer.SEARCH:
            self.search_activated.emit()

        self.layer_changed.emit(new_layer)
        self.update_hints()

    def register_widgets(self, layer, widgets):
        """Регистрация виджетов для навигации в слое"""
        if not isinstance(layer, NavigationLayer):
            raise ValueError(f"Неверный слой навигации: {layer}")

        self.layer_widgets[layer] = widgets
        logger.info(f"📋 Зарегистрировано {len(widgets)} виджетов для слоя {layer.name}")

        # Автоматически устанавливаем фокус если это текущий слой
        if widgets and self.current_layer == layer:
            self.set_focus(layer, 0)

    def set_focus(self, layer, index):
        """Установка фокуса на виджет в указанном слое"""
        if layer != self.current_layer:
            logger.warning(f"⚠️ Попытка установить фокус на неактивном слое: {layer.name}")
            return

        widgets = self.layer_widgets.get(layer, [])
        if not widgets:
            logger.warning(f"⚠️ Нет виджетов в слое {layer.name}")
            return

        if index < 0 or index >= len(widgets):
            logger.error(f"❌ Неверный индекс фокуса: {index} для слоя {layer.name}")
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

        self.focus_index[layer] = index
        self.focus_changed.emit(widget)

        logger.debug(f"🎯 Фокус установлен на индекс {index} в слое {layer.name}")

    def clear_focus(self, layer):
        """Очистка фокуса в указанном слое"""
        widgets = self.layer_widgets.get(layer, [])
        for widget in widgets:
            widget.setProperty("focused", False)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.clearFocus()

    def activate_focused_widget(self):
        """Активация currently сфокусированного виджета"""
        layer = self.current_layer
        idx = self.focus_index.get(layer, 0)
        widgets = self.layer_widgets.get(layer, [])

        if not widgets or idx < 0 or idx >= len(widgets):
            logger.warning("⚠️ Нет виджета для активации")
            return

        widget = widgets[idx]
        logger.debug(f"🎮 Активация виджета: {widget}")

        if isinstance(widget, QPushButton):
            QTimer.singleShot(0, widget.click)
            return

        if hasattr(widget, 'action') and callable(widget.action):
            widget.action()
            return

        widget.setFocus(Qt.FocusReason.TabFocusReason)

    # ==================== ПОДСКАЗКИ ====================

    def set_hint_widget(self, widget):
        """Установка виджета для отображения подсказок"""
        if widget is None:
            self.hint_widget = None
            return

        if not hasattr(widget, "setText"):
            raise ValueError("Виджет подсказок должен поддерживать setText()")

        self.hint_widget = widget
        self.update_hints()
        logger.info("💡 Виджет подсказок установлен")

    def update_hints(self):
        """Обновление текста подсказок для текущего слоя"""
        if not self.hint_widget:
            return

        # Пользовательские подсказки имеют приоритет
        if self.current_layer in self.hint_overrides:
            text = self.hint_overrides[self.current_layer]
        else:
            # Стандартные подсказки для каждого слоя
            hints = {
                NavigationLayer.MAIN: "↓: Настройки  |  A: Запустить  |  Y: Поиск  |  B: Выход",
                NavigationLayer.SETTINGS: "↑: Главный экран  |  ←/→: Навигация  |  A: Выбрать  |  B: Назад",
                NavigationLayer.SEARCH: "B: Назад  |  Enter: Поиск  |  Стрелки: Навигация",
                NavigationLayer.GAME_INFO: "←/→: Переключение кнопок  |  A: Выбрать  |  B: Назад в библиотеку",
            }
            text = hints.get(self.current_layer, "")

        try:
            self.hint_widget.setText(text)
            logger.debug(f"💡 Обновлены подсказки для {self.current_layer.name}")
        except Exception as e:
            logger.error(f"❌ Ошибка обновления подсказок: {e}")

    # ==================== СЛУЖЕБНЫЕ МЕТОДЫ ====================

    def return_to_previous_layer(self):
        """Возврат к предыдущему слою"""
        if self.previous_layer:
            logger.info(f"↩️ Возврат к предыдущему слою: {self.previous_layer.name}")
            self.switch_layer(self.previous_layer)

    def move_focus(self, direction):
        """Перемещение фокуса в указанном направлении"""
        if not (-1 <= direction <= 1):
            raise ValueError("Направление должно быть -1 или 1")

        layer = self.current_layer
        widgets = self.layer_widgets.get(layer, [])
        if not widgets:
            return

        current_idx = self.focus_index[layer]
        new_idx = (current_idx + direction) % len(widgets)
        self.set_focus(layer, new_idx)
