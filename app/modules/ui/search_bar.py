import json
import os
import logging
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit,
    QListWidget, QListWidgetItem
)

# Добавляем логгер
logger = logging.getLogger('ArcadeDeck')

class SearchBar(QWidget):
    """Search bar widget with auto-complete functionality"""
    # Signal emits list of search results
    searchUpdated = pyqtSignal(list)

    def __init__(self, open_game_info_callback=None, parent=None):
        super().__init__(parent)
        self.open_game_info_callback = open_game_info_callback
        self.games_data = []
        self._init_ui()

    def _init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)

        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск игр...")
        self.search_input.textChanged.connect(self.on_search_text_changed)
        layout.addWidget(self.search_input)

        # Results list
        self.results_list = QListWidget()
        self.results_list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
        self.results_list.itemClicked.connect(self.on_result_clicked)
        layout.addWidget(self.results_list)
        self.results_list.hide()  # Hidden by default

    def set_game_list(self, games):
        """Set game list from centralized manager - ВСЕ игры из реестра"""
        try:
            # Получаем ВСЕ игры из реестра (включая не установленные)
            from app.modules.module_logic.game_data_manager import get_game_data_manager
            manager = get_game_data_manager()

            if manager:
                # Используем метод для получения всех доступных игр из реестра
                all_available_games = manager.get_all_available_games()
                self.games_data = all_available_games
                logger.info(f"[SearchBar] Загружено {len(all_available_games)} игр из реестра (все доступные)")
            else:
                # Fallback для обратной совместимости
                self.games_data = [g for g in (games or []) if isinstance(g, dict)]
                logger.warning("[SearchBar] Используем fallback данные игр")

        except Exception as e:
            logger.error(f"[SearchBar] Ошибка при set_game_list: {e}")
            self.games_data = [g for g in (games or []) if isinstance(g, dict)]

    def on_search_text_changed(self, text):
        """Handle search text changes - ищем игры, которые НАЧИНАЮТСЯ с текста"""
        text = (text or "").strip().lower()

        # Clear results for empty query
        if not text:
            self.results_list.hide()
            self.searchUpdated.emit([])
            return

        # Filter matching games - startsWith вместо contains
        results = [
            game for game in self.games_data
            if (game.get("title") or "").lower().startswith(text)
        ]

        # Update UI and emit signal
        self.searchUpdated.emit(results)
        self.update_results_list(results)

    def update_results_list(self, results):
        """Update results list UI"""
        self.results_list.clear()

        if results:
            for game in results:
                # Показываем статус установки в результатах поиска
                title = game.get("title", "Без названия")
                if game.get("is_installed"):
                    title = f"✅ {title}"
                else:
                    title = f"⬇️ {title}"

                item = QListWidgetItem(title)
                item.setData(1000, game)
                self.results_list.addItem(item)
            self.results_list.show()
        else:
            self.results_list.hide()

    def on_result_clicked(self, item):
        """Handle result item click"""
        game_data = item.data(1000)
        if not game_data:
            return

        # Hide results list
        try:
            self.results_list.hide()
        except Exception:
            pass

        # Call callback if available
        if callable(self.open_game_info_callback):
            try:
                self.open_game_info_callback(game_data)
            except Exception as e:
                logger.error(f"[SearchBar] Ошибка callback: {e}")

    def reset_search(self):
        """Reset search state"""
        try:
            # Block signals during reset
            self.search_input.blockSignals(True)
            self.search_input.clear()
            self.search_input.blockSignals(False)

            # Clear results
            self.results_list.clear()
            self.results_list.hide()

            # Notify subscribers
            self.searchUpdated.emit([])
        except Exception as e:
            logger.error(f"[SearchBar] Ошибка reset_search: {e}")
