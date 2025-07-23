# common.py
import os
import sys
from PyQt5.QtCore import QFile, QTextStream

# Версия программы (stanle или beta)
APP_VERSION = "0.1.6.2.2b (62) BETA"
USER_HOME = os.path.expanduser("~")

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONTENT_DIR = os.path.join(BASE_DIR, "Content")
STYLES_DIR = os.path.join(BASE_DIR, "data", "style")
GUIDES_JSON_PATH = os.path.join(CONTENT_DIR, "guides.json")
GAME_LIST_GUIDE_JSON_PATH = os.path.join(CONTENT_DIR, "game-list-guides.json")
DARK_STYLE = os.path.join(STYLES_DIR, "Dark-style.qss")
LIGHT_STYLE = os.path.join(STYLES_DIR, "Light-style.qss")

os.makedirs(CONTENT_DIR, exist_ok=True)
os.makedirs(STYLES_DIR, exist_ok=True)

def load_stylesheet(filename):
    file = QFile(filename)
    if file.exists() and file.open(QFile.ReadOnly | QFile.Text):
        stream = QTextStream(file)
        return stream.readAll()
    return ""
