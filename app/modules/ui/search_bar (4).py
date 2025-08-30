import json
import os
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit,
    QListWidget, QListWidgetItem
)

# Default paths for registry file
DEFAULT_REG_PATHS = [
    os.path.join("app", "registry", "registry_games.json"),
    os.path.join(os.path.dirname(__file__), "..", "registry", "registry_games.json"),
    os.path.join(os.path.dirname(__file__), "..", "..", "registry", "registry_games.json"),
    os.path.join(os.path.abspath(os.sep), "mnt", "data", "registry_games.json"),
]


def find_registry_path():
    """Find registry file path"""
    for path in DEFAULT_REG_PATHS:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            return abs_path
    return os.path.abspath(DEFAULT_REG_PATHS[0])


REGISTRY_PATH = find_registry_path()


class SearchBar(QWidget):
    """Search bar widget with auto-complete functionality"""
    # Signal emits list of search results
    searchUpdated = pyqtSignal(list)

    def __init__(self, open_game_info_callback=None, parent=None):
        super().__init__(parent)
        self.open_game_info_callback = open_game_info_callback
        self.registry_games = self.load_games_from_registry()
        self.installed_games = []
        self.games_data = list(self.registry_games)
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

    def load_games_from_registry(self):
        """Load games from registry file"""
        if not os.path.exists(REGISTRY_PATH):
            print(f"[SearchBar] ⚠️ Не найден файл {REGISTRY_PATH}")
            return []

        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle different registry formats
            if isinstance(data, dict):
                games = data.get("games", [])
            elif isinstance(data, list):
                games = data
            else:
                print(f"[SearchBar] ❌ Неподдерживаемый формат: {type(data)}")
                games = []

            # Normalize game data
            normalized = []
            for game in games:
                if not isinstance(game, dict):
                    continue

                # Ensure title exists
                if "title" not in game:
                    game["title"] = "Без названия"

                # Ensure ID exists
                if "id" not in game:
                    game["id"] = game["title"].lower().replace(" ", "_")

                normalized.append(game)

            return normalized
        except Exception as e:
            print(f"[SearchBar] ❌ Ошибка чтения JSON: {e}")
            return []

    def set_game_list(self, games):
        """Set game list from external source"""
        try:
            self.installed_games = [
                g for g in (games or []) if isinstance(g, dict)
            ]

            # Merge registry and installed games
            registry_by_id = {
                g["id"]: g for g in self.registry_games if "id" in g
            }
            merged = list(registry_by_id.values())

            # Add installed games not in registry
            for game in self.installed_games:
                game_id = game.get("id") or game["title"].lower().replace(" ", "_")
                if game_id not in registry_by_id:
                    merged.append(game)

            self.games_data = merged
        except Exception as e:
            print(f"[SearchBar] ❌ Ошибка при set_game_list: {e}")
            self.games_data = list(self.registry_games)

    def on_search_text_changed(self, text):
        """Handle search text changes"""
        text = (text or "").strip().lower()

        # Clear results for empty query
        if not text:
            self.results_list.hide()
            self.searchUpdated.emit([])
            return

        # Filter matching games
        results = [
            game for game in self.games_data
            if text in (game.get("title") or "").lower()
        ]

        # Update UI and emit signal
        self.searchUpdated.emit(results)
        self.update_results_list(results)

    def update_results_list(self, results):
        """Update results list UI"""
        self.results_list.clear()

        if results:
            for game in results:
                item = QListWidgetItem(game.get("title", "Без названия"))
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
                print(f"[SearchBar] Ошибка callback: {e}")

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
            print(f"[SearchBar] Ошибка reset_search: {e}")