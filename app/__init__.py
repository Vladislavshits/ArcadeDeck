import os
import sys

# Установка централизованного кеша
cache_dir = os.path.join(os.path.expanduser("~"), "ArcadeDeck", "app", "caches")
os.makedirs(cache_dir, exist_ok=True)

# Для Python 3.8+
if hasattr(sys, 'pycache_prefix'):
    sys.pycache_prefix = cache_dir

# Для всех версий Python
os.environ['PYTHONPYCACHEPREFIX'] = cache_dir

# Отключаем создание .pyc файлов в текущей директории
sys.dont_write_bytecode = True

# Ваши обычные импорты и код
from .ui_assets.theme_manager import theme_manager
from updater import Updater, UpdateDialog
from navigation import NavigationController
from navigation import NavigationLayer
from settings import app_settings
from enum import Enum, auto
