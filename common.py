# common.py
import os
import sys
from PyQt5.QtCore import QFile, QTextStream

APP_VERSION = "0.1.6.2 BETA"
USER_HOME = os.path.expanduser("~")
STYLES_DIR = os.path.join(USER_HOME, "PixelDeck", "data", "style")
DARK_STYLE = os.path.join(STYLES_DIR, "Dark-style.qss")
LIGHT_STYLE = os.path.join(STYLES_DIR, "Light-style.qss")

def load_stylesheet(filename):
    """Загружает файл стилей"""
    file = QFile(filename)
    if file.exists() and file.open(QFile.ReadOnly | QFile.Text):
        stream = QTextStream(file)
        return stream.readAll()
    return ""
